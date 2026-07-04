# KnowMesh — Full Phase-by-Phase Implementation Plan

## Phase Overview

| Phase | Title | Core Deliverable |
|---|---|---|
| **1** | Ingestion Pipeline | Upload → parse → chunk → embed → store (end-to-end data flow) |
| **2** | Entity Extraction | LLM-based NER populating the graph layer |
| **3** | Query Path Hardening | Concurrent search, SSE streaming, citation quality |
| **4** | Auth & User Scoping | JWT auth, per-user data isolation |
| **5** | Frontend | Upload UI, document list, query interface, graph visualization |
| **6** | Observability & Error Handling | structlog, Prometheus metrics, global exception handlers |
| **7** | CI/CD & Test Expansion | GitHub Actions pipeline, coverage enforcement |

**Dependency chain:** 1 → 2 → 3 → 4 → 5 → 6 → 7. Each phase depends on the previous being complete. Phase 4 (auth) could technically run in parallel with 2–3, but sequencing it after query hardening means the frontend (phase 5) connects to a fully functional, authenticated API.

---

# Phase 1 — Ingestion Pipeline

## Abstract Overview

The system currently has all ingestion *building blocks* (document loaders, chunkers, embedder, repositories, S3 client) but no code that connects them. There is no upload endpoint, no orchestration function, and no worker job. This phase builds the connective tissue: an upload API, an `IngestionPipeline` orchestrator, a background job function, and batch embedding logic. After this phase, a user can upload a file through the API and have it fully processed into searchable, embedded chunks.

## Final Objective

- `POST /documents/upload` accepts multipart files, validates them, stores in S3, creates a `Document` record (status: `queued`), enqueues a background job
- `process_document(doc_id)` worker job runs the full pipeline: download → parse → chunk → embed (batched) → store chunks with embeddings → update status
- Document status lifecycle: `queued` → `processing` → `completed` | `failed`
- Duplicate detection via `file_hash` (SHA-256)
- Batch embedding with configurable batch size and retry/backoff for Voyage API rate limits

---

## Step 1.1 — Upload schemas

**File:** `backend/schemas/document.py`

**New class:** `UploadResponse(BaseModel)`
- Fields: `id: UUID`, `filename: str`, `status: str`, `file_size: int`, `file_hash: str`, `created_at: datetime`
- `model_config = ConfigDict(from_attributes=True)`

**Why:** The upload endpoint needs a response schema distinct from `DocumentResponse` — it returns immediately before processing completes, so fields like `chunk_count` and `error` are irrelevant. Keeping a separate schema makes the API contract explicit: the client knows this is a "just received" response.

**Change to existing class `DocumentCreate`:** Add `user_id: UUID | None = None` field (optional for now, required in Phase 4). This allows the orchestrator to pass ownership through the existing create flow.

**Connects to:** Upload endpoint (step 1.5), `DocumentRepository.create()` which already accepts `DocumentCreate`.

---

## Step 1.2 — Ingestion pipeline orchestrator

**File:** `backend/rag/ingestion/pipeline.py` (new)

**New class:** `IngestionPipeline`

```
__init__(
    self,
    s3: S3Client,
    chunk_repo: ChunkRepository,
    document_repo: DocumentRepository,
    embedder: Embedder,
    loader_registry: LoaderRegistry,
    chunker: BaseChunker,
    embed_batch_size: int = 96,
)
```

**New methods:**

| Method | Purpose |
|---|---|
| `async process(self, document_id: UUID) -> None` | Main entry point called by the worker. Orchestrates the full pipeline. |
| `async _download(self, s3_key: str, dest: Path) -> Path` | Delegates to `S3Client.download()`. |
| `async _parse(self, path: Path, document_id: UUID) -> list[Document]` | Calls `LoaderRegistry` to get the right loader, calls `loader.load()`. |
| `async _chunk(self, documents: list[Document]) -> list[Chunk]` | Iterates documents, calls `self._chunker.chunk()` on each, assigns sequential indices. |
| `async _embed_and_store(self, chunks: list[Chunk], document_id: UUID) -> int` | Batches chunks into groups of `embed_batch_size`, calls `Embedder.embed()` per batch, constructs ORM `Chunk` objects with embeddings, calls `ChunkRepository.insert_many()`. Returns total chunk count. |
| `async _update_status(self, document_id: UUID, status: str, **kwargs) -> None` | Calls `DocumentRepository.update()` with status + optional fields (chunk_count, error). |

**`process()` flow:**
```
1. doc = document_repo.get_by_id(document_id)
2. _update_status(document_id, "processing")
3. temp_path = _download(doc.s3_key, tmp_dir / doc.filename)
4. pages = _parse(temp_path, document_id)
5. dataclass_chunks = _chunk(pages)
6. count = _embed_and_store(dataclass_chunks, document_id)
7. _update_status(document_id, "completed", chunk_count=count)
8. cleanup temp file
   on any exception:
     _update_status(document_id, "failed", error=str(e))
     log and re-raise
```

**Why this design:**
- The pipeline is a plain class with injectable dependencies (same pattern as `RetrievalService` in `backend/rag/retrieval.py`). This makes it testable with mocks and keeps it decoupled from FastAPI.
- `_embed_and_store` handles batching internally. Voyage API has rate limits — 96 texts per batch is a safe default (Voyage allows up to 128 per call on `voyage-4-lite`). The batch loop includes `asyncio.sleep(0.1)` between batches as a simple rate-limit buffer.
- Status transitions are explicit and always happen, even on failure. The `try/except` in `process()` guarantees `failed` status is set.
- Temp file cleanup uses `tempfile.TemporaryDirectory` as a context manager — no manual cleanup needed.

**Connects to:** Worker job (step 1.3) calls `pipeline.process()`. Upload endpoint (step 1.5) creates the `Document` record that `process()` operates on. `Embedder` (`backend/rag/embedding.py`) is called per-batch. `ChunkRepository.insert_many()` (`backend/repositories/chunk.py`) persists the chunks. `DocumentRepository` (`backend/repositories/document.py`) tracks status.

---

## Step 1.3 — Worker job function

**File:** `backend/workers/jobs.py` (new)

**New function:** `process_document(document_id: str) -> None`

```
1. Create a fresh async event loop (RQ workers are sync)
2. Inside the loop:
   a. Create AsyncSession via get_db_session()
   b. Instantiate DocumentRepository, ChunkRepository, Embedder, IngestionPipeline
   c. Await pipeline.process(UUID(document_id))
3. Close session, dispose engine
```

**Why a separate file:** The existing `backend/workers/worker.py` only contains the `run_worker()` entry point that starts the RQ `Worker` listener. Job functions are what get enqueued — they must be importable by both the enqueuer (API process) and the worker process. Separating them follows RQ convention.

**Why a fresh event loop:** RQ is synchronous. The `process_document` function runs in a regular thread. But `IngestionPipeline.process()` is async (it calls async S3, async DB, async LLM). We bridge with `asyncio.run()` which creates and manages a temporary event loop.

**Connects to:** `IngestionPipeline` (step 1.2) — the job function is a thin wrapper that sets up dependencies and delegates. Upload endpoint (step 1.5) enqueues this function via `queue.enqueue(process_document, str(doc.id))`.

---

## Step 1.4 — Update worker entry point

**File:** `backend/workers/worker.py`

**Change:** Import `backend.workers.jobs` at module level so RQ can resolve the job function by its dotted path. No other changes needed — RQ discovers functions by import path.

**Why:** RQ serializes jobs as `module.function_name` strings. The worker process must be able to import `backend.workers.jobs.process_document`. The import ensures the module is loaded.

**Connects to:** Job function (step 1.3), upload endpoint (step 1.5).

---

## Step 1.5 — Upload endpoint

**File:** `backend/app/api/rag.py`

**New route handler:**

```python
@router.post("/documents/upload", response_model=UploadResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    strategy: str = Form("recursive"),
    document_repo: DocumentRepository = Depends(get_document_repo),
    s3: S3Client = Depends(get_s3_client),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
```

**Handler flow:**
```
1. Validate file extension against LoaderRegistry.supported_extensions
   → 400 if unsupported
2. Read file bytes, validate size <= settings.max_upload_size_mb * 1024 * 1024
   → 413 if too large
3. Compute SHA-256 hash of file bytes
4. Check document_repo.get_by_hash(file_hash)
   → if found with status "completed", return existing document (dedup)
   → if found with status "processing"/"queued", return existing (already in flight)
5. s3_key = f"documents/{uuid4()}/{file.filename}"
6. await s3.upload(data, s3_key)
7. Create DocumentCreate(filename, file_type, file_size, file_hash, strategy, meta={"s3_key": s3_key})
8. doc = await document_repo.create(data)
9. queue = rq.Queue(settings.redis_queue_name, connection=redis)
10. queue.enqueue("backend.workers.jobs.process_document", str(doc.id))
11. Return UploadResponse from doc
```

**New imports needed in `rag.py`:**
- `from fastapi import UploadFile, File, Form`
- `from backend.app.core.s3 import get_s3_client`
- `from backend.app.core.redis import get_redis`
- `from backend.app.config import Settings, get_settings`
- `from backend.rag.ingestion.document_loader import LoaderRegistry`
- `import hashlib, rq`

**Why this design:**
- File validation happens *before* S3 upload — no wasted storage for rejected files.
- Dedup check uses the existing `DocumentRepository.get_by_hash()` method (already implemented, currently unused). This prevents re-processing identical files.
- The S3 key includes a UUID prefix to avoid filename collisions (two users uploading "notes.pdf" get distinct keys).
- `strategy` is a form parameter (not part of the file), defaulting to `"recursive"` to match the `Document` model's default.
- The endpoint returns immediately after enqueueing — the client polls `GET /documents/{id}` for status updates.

**Connects to:** `DocumentRepository.create()` and `get_by_hash()` (existing), `S3Client.upload()` (existing), RQ queue (existing Redis connection), job function (step 1.3).

---

## Step 1.6 — Add `s3_key` to Document model and migration

**File:** `backend/app/models/document.py`

**Change:** Add column `s3_key: Mapped[str]` (String, nullable=False, default=""). This stores the S3 object key so the worker knows where to download the file.

**File:** `backend/migrations/versions/0003_document_s3_key.py` (new)

**`upgrade()`:** `op.add_column("documents", sa.Column("s3_key", sa.String(), nullable=False, server_default=""))`

**`downgrade()`:** `op.drop_column("documents", "s3_key")`

**Why:** The `Document` model currently has no field to track where the source file lives in object storage. The `meta` JSONB field could store it, but `s3_key` is a first-class concern — every document has exactly one source file. Making it a proper column enables indexing and querying.

**Connects to:** Upload endpoint (step 1.5) writes `s3_key` into `DocumentCreate.meta` or directly. Pipeline (step 1.2) reads it back to download.

---

## Step 1.7 — Wire pipeline dependencies

**File:** `backend/app/dependencies.py`

**New function:**
```python
async def get_ingestion_pipeline(
    chunk_repo: ChunkRepository = Depends(get_chunk_repo),
    document_repo: DocumentRepository = Depends(get_document_repo),
    manager: LLMManager = Depends(get_llm_manager),
    s3: S3Client = Depends(get_s3_client),
    settings: Settings = Depends(get_settings),
) -> IngestionPipeline:
```

Returns `IngestionPipeline(s3=s3, chunk_repo=chunk_repo, document_repo=document_repo, embedder=Embedder(manager), loader_registry=default_registry, chunker=RecursiveChunker())`.

**Why:** Follows the existing DI pattern. The pipeline is composed from the same building blocks as `get_retrieval_service`. The chunker defaults to `RecursiveChunker` but the `strategy` field on the `Document` record could select `SemanticChunker` instead (future enhancement).

**Connects to:** Upload endpoint (step 1.5) doesn't need the pipeline directly (it only enqueues), but this dependency is useful for synchronous ingestion paths or admin endpoints.

---

## Step 1.8 — Tests

**File:** `tests/rag/test_pipeline.py` (new)

**Test functions (all fully mocked, no live services):**

| Test | What it verifies |
|---|---|
| `test_process_happy_path` | Mock all deps. Verify: download called, parse called, chunk called, embed called with batched texts, insert_many called with chunks+embeddings, status updated to "completed" with correct chunk_count. |
| `test_process_sets_failed_on_error` | Mock embedder to raise. Verify status updated to "failed" with error message. |
| `test_process_embed_batching` | Create 200 chunks, batch_size=96. Verify embed called 3 times (96, 96, 8). |
| `test_process_empty_document` | Mock parser to return empty list. Verify status "completed" with chunk_count=0, no embed call. |

**File:** `tests/api/test_upload.py` (new)

| Test | What it verifies |
|---|---|
| `test_upload_success` | POST multipart file, mock S3 + repo + redis. Verify 201, response shape, S3 upload called, document created, job enqueued. |
| `test_upload_unsupported_extension` | Upload `.xyz` file. Verify 400. |
| `test_upload_exceeds_size_limit` | Upload oversized file. Verify 413. |
| `test_upload_duplicate_returns_existing` | Mock `get_by_hash` to return existing completed doc. Verify 200 (not 201) with existing doc's ID. |

**Connects to:** Pipeline (step 1.2), upload endpoint (step 1.5).

---

# Phase 2 — Entity Extraction

## Abstract Overview

The graph layer (entities, relations, chunk-entity links) has a complete schema, repositories, and `GraphService` — but nothing populates it. This phase adds LLM-based named entity recognition (NER) that extracts structured entities and relations from each chunk's text, then links them to their source chunks. After this phase, `GraphService.search()` returns real results, contributing the 15% graph weight to hybrid retrieval.

## Final Objective

- An `EntityExtractor` class that takes chunk text and returns structured entities + relations via LLM
- Extraction runs as part of the ingestion pipeline (after chunking, before or alongside embedding)
- Entities are deduplicated within a document (same name → same entity row)
- Chunk-entity junction links are created
- Extraction prompt is configurable and stored in `backend/prompts/`

---

## Step 2.1 — Entity extraction prompt

**File:** `backend/prompts/system/entity_extractor.md` (new)

**Content:** A system prompt instructing the LLM to extract entities and relations from text as structured JSON:

```
You are a knowledge graph extractor. Given a text chunk, extract:
1. entities: list of {name, type} where type is one of: PERSON, ORGANIZATION, CONCEPT, EVENT, LOCATION, TECHNOLOGY, OTHER
2. relations: list of {source, target, relation_type} where source/target are entity names

Return ONLY valid JSON: {"entities": [...], "relations": [...]}
Rules:
- Normalize entity names (title case, strip whitespace)
- Merge duplicate entities within this chunk
- Keep relation_type concise (1-3 words)
- If no entities found, return {"entities": [], "relations": []}
```

**Why:** A dedicated prompt file follows the existing convention (`backend/prompts/system/rag_generator.md`). The JSON output format is parsed programmatically. Constraining entity types prevents unbounded type proliferation.

**Connects to:** `EntityExtractor` (step 2.2) loads this prompt via `load_prompt("entity_extractor")`.

---

## Step 2.2 — EntityExtractor class

**File:** `backend/rag/extraction.py` (new)

**New class:** `EntityExtractor`

```python
__init__(self, manager: LLMManager)
```

**New methods:**

| Method | Signature | Purpose |
|---|---|---|
| `extract` | `async extract(self, chunk_text: str) -> ExtractedGraph` | Sends chunk text + system prompt to LLM, parses JSON response, returns typed dataclass. |
| `_parse_response` | `_parse_response(self, raw: str) -> ExtractedGraph` | JSON parse with fallback: if JSON is malformed, attempt to extract JSON from markdown code blocks. Returns empty `ExtractedGraph` on total failure. |

**New dataclass:** `ExtractedGraph`
- `entities: list[dict]` — each `{"name": str, "type": str}`
- `relations: list[dict]` — each `{"source": str, "target": str, "relation_type": str}`

**Why:** Separating extraction from storage keeps the class single-purpose and testable. The `LLMManager.generate()` method (already exists, used by `Generator`) handles the LLM call. JSON parsing has a fallback because LLMs sometimes wrap JSON in markdown fences.

**LLM call details:** Uses `manager.generate(system_prompt, chunk_text, temperature=0.0, max_tokens=512)`. Temperature 0 for deterministic extraction. `max_tokens=512` is sufficient for a single chunk's entities.

**Connects to:** `LLMManager.generate()` (existing `backend/app/core/llm_manager.py`), `load_prompt()` (existing `backend/rag/generator.py`). Pipeline integration (step 2.3) calls `extract()` per chunk.

---

## Step 2.3 — Integrate extraction into ingestion pipeline

**File:** `backend/rag/ingestion/pipeline.py`

**Changes to `IngestionPipeline.__init__()`:** Add parameters:
- `graph_service: GraphService`
- `extractor: EntityExtractor | None = None`

If `extractor` is `None`, graph extraction is skipped (graceful degradation — useful when no LLM is configured for extraction).

**New method:** `async _extract_and_store_graph(self, chunks: list[Chunk], document_id: UUID, orm_chunks: list[Chunk]) -> None`

```
1. For each dataclass chunk (parallelized with asyncio.gather, semaphore=5):
   a. Call extractor.extract(chunk.text) → ExtractedGraph
   b. Collect all entities and relations
2. Deduplicate entities by normalized name within the document
3. Create Entity ORM objects (with document_id)
4. Create Relation ORM objects (resolving source/target names to entity IDs)
5. Create ChunkEntity links (mapping chunk index to entity IDs)
6. Call graph_service.store(entities, relations, links)
```

**Change to `process()` flow:** After `_embed_and_store` returns, add:
```python
if self._extractor:
    await self._extract_and_store_graph(dataclass_chunks, document_id, orm_chunks)
```

**Why semaphore=5:** Extraction makes one LLM call per chunk. A 50-page document might produce 100+ chunks. Without concurrency control, this would hammer the LLM API. A semaphore of 5 allows 5 concurrent extraction calls — good throughput without triggering rate limits.

**Why deduplication:** The same entity (e.g., "Machine Learning") may appear in multiple chunks. Without dedup, we'd create N entity rows for the same concept. Dedup by normalized name (lowercase, stripped) within a document ensures one entity row per unique name.

**Connects to:** `GraphService.store()` (existing `backend/rag/graph/service.py`), `EntityExtractor` (step 2.2), `Entity`/`Relation`/`ChunkEntity` ORM models (existing).

---

## Step 2.4 — Update pipeline dependency wiring

**File:** `backend/app/dependencies.py`

**Change to `get_ingestion_pipeline()`:** Add `graph_service: GraphService = Depends(get_graph_service)` parameter. Create `EntityExtractor(manager)` and pass both to `IngestionPipeline`.

**Connects to:** Pipeline (step 2.3), `GraphService` DI (existing).

---

## Step 2.5 — Tests

**File:** `tests/rag/test_extraction.py` (new)

| Test | What it verifies |
|---|---|
| `test_extract_valid_json` | Mock LLM to return valid JSON. Verify parsed entities and relations. |
| `test_extract_markdown_wrapped_json` | Mock LLM to return ````json\n{...}\n````. Verify fallback parser extracts correctly. |
| `test_extract_malformed_json` | Mock LLM to return garbage. Verify returns empty `ExtractedGraph`. |
| `test_extract_empty_text` | Empty input → empty output, no LLM call. |

**File:** `tests/rag/test_pipeline.py` (extend existing from Phase 1)

| Test | What it verifies |
|---|---|
| `test_process_with_extraction` | Mock extractor + graph_service. Verify extractor called per chunk, graph_service.store called with entities/relations/links. |
| `test_process_extraction_failure_continues` | Mock extractor to raise. Verify pipeline still completes (extraction failure doesn't block chunk storage). |
| `test_process_no_extractor_skips_graph` | Pipeline created with `extractor=None`. Verify no extraction attempted. |

**Connects to:** `EntityExtractor` (step 2.2), pipeline integration (step 2.3).

---

# Phase 3 — Query Path Hardening

## Abstract Overview

The query path works end-to-end but has three production-readiness gaps: search queries run sequentially (when they're independent), answers return as a single blocking response (no streaming), and citations are truncated at 200 chars without sentence awareness. This phase addresses all three.

## Final Objective

- Vector, FTS, and graph searches run concurrently via `asyncio.gather()`
- New SSE streaming endpoint for token-by-token answer delivery
- Citations use sentence-boundary-aware snippet extraction
- Graph search respects `document_ids` filter and can discover chunks that vector/FTS missed

---

## Step 3.1 — Concurrent search

**File:** `backend/rag/retrieval.py`

**Change to `RetrievalService._search()`:**

Replace the three sequential `await` calls with:
```python
vector_results, fts_results, graph_results = await asyncio.gather(
    self._chunk_repo.search_vector(query_embedding, top_k=top_k, document_ids=document_ids),
    self._chunk_repo.search_fts(query, top_k=top_k, document_ids=document_ids),
    self._graph.search(query, top_k=top_k, document_ids=document_ids),
)
```

**Why:** The three searches are independent — they query different indexes/tables with no data dependency. Running them concurrently cuts latency from `sum(T_vec, T_fts, T_graph)` to `max(T_vec, T_fts, T_graph)`. In practice, this is roughly a 2-3x speedup on the search phase.

**New import:** `import asyncio` at the top of the file.

**Connects to:** `GraphService.search()` needs a `document_ids` parameter (step 3.2).

---

## Step 3.2 — Graph search: document_ids filter + discovery

**File:** `backend/rag/graph/service.py`

**Change to `GraphService.search()`:** Add `document_ids: list[UUID] | None = None` parameter. Pass through to `self._entities.search_by_text(query_text, document_ids=document_ids)`.

**File:** `backend/repositories/entity.py`

**Change to `EntityRepository.search_by_text()`:** Add `document_ids: list[UUID] | None = None` parameter. When provided, add `.where(Entity.document_id.in_(document_ids))` to the query.

**File:** `backend/rag/retrieval.py`

**Change to `_merge_scores()`:** Currently graph results only boost chunks already found by vector/FTS (`if chunk_id in chunk_map`). Change to also add graph-discovered chunks to the result set:

```python
for chunk_id, score in graph_results:
    if chunk_id in chunk_map:
        scores[chunk_id] = scores.get(chunk_id, 0.0) + w_graph * score
    else:
        # Graph can surface chunks vector/FTS missed
        scores[chunk_id] = w_graph * score
```

For graph-discovered chunks not in `chunk_map`, we need to fetch them. Add a post-merge step:
```python
missing_ids = [cid for cid in scores if cid not in chunk_map]
if missing_ids:
    missing = await self._chunk_repo.get_by_ids(missing_ids)
    for c in missing:
        chunk_map[c.id] = c
```

This requires `_merge_scores` to become async. Update the call site in `_search()` accordingly.

**Why:** The current design makes graph search a pure booster — it can only improve scores of already-found chunks. This means graph search adds zero value when vector/FTS miss a relevant chunk that graph would find. Allowing discovery makes the 15% graph weight meaningful even when the other two signals fail.

**Connects to:** Concurrent search (step 3.1) passes `document_ids` through. `ChunkRepository.get_by_ids()` (existing) fetches missing chunks.

---

## Step 3.3 — Sentence-boundary citation snippets

**File:** `backend/rag/retrieval.py`

**New static method:** `_extract_snippet(text: str, max_chars: int = 200) -> str`

```python
import re
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')

@staticmethod
def _extract_snippet(text: str, max_chars: int = 200) -> str:
    sentences = _SENTENCE_RE.split(text)
    snippet = ""
    for sentence in sentences:
        if len(snippet) + len(sentence) + 1 > max_chars:
            break
        snippet = (snippet + " " + sentence).strip()
    return snippet or text[:max_chars]
```

**Change to `query()`:** Replace `c.text[:200]` with `self._extract_snippet(c.text)`.

**Why:** Naive `text[:200]` can cut mid-word or mid-sentence, producing garbled citations. Sentence-boundary truncation gives the user a clean, readable snippet that ends at a natural break.

**Connects to:** `Citation` schema (existing `backend/schemas/query.py`) — no change needed, the `text` field just gets better content.

---

## Step 3.4 — SSE streaming endpoint

**File:** `backend/rag/generator.py`

**New method:** `async generate_stream(self, query: str, contexts: list[str], ...) -> AsyncIterator[str]`

```python
async def generate_stream(self, query, contexts, temperature=0.3, max_tokens=1024):
    system_prompt = load_prompt("rag_generator")
    user_prompt = self._build_user_prompt(query, contexts)
    async for token in self._manager.generate_stream(system_prompt, user_prompt, temperature, max_tokens):
        yield token
```

**File:** `backend/app/core/llm_manager.py`

**New method on `LLMManager`:** `async generate_stream(self, ...) -> AsyncIterator[str]`

Uses `AsyncOpenAI.chat.completions.create(..., stream=True)` and yields `choice.delta.content` tokens.

**New method on `GenerateClient` Protocol:** `async generate_stream(...) -> AsyncIterator[str]`

**New method on `OpenAICompatibleClient`:** Implements `generate_stream` using the OpenAI streaming API.

**File:** `backend/rag/retrieval.py`

**New method on `RetrievalService`:** `async query_stream(self, query, document_ids, top_k) -> AsyncIterator[str]`

Same as `query()` but yields SSE-formatted events:
```
event: search_done
data: {"chunk_count": N}

event: token
data: {"text": "..."}

event: done
data: {"citations": [...]}
```

**File:** `backend/app/api/rag.py`

**New route handler:**
```python
@router.post("/query/stream")
async def query_stream(body: QueryRequest, service: RetrievalService = Depends(get_retrieval_service)):
    return StreamingResponse(service.query_stream(...), media_type="text/event-stream")
```

**New import:** `from fastapi.responses import StreamingResponse`

**Why:** For long answers (common with study material), users see nothing for seconds while the LLM generates. Streaming shows tokens as they arrive, dramatically improving perceived latency. SSE is simpler than WebSocket, works with HTTP/2, and is supported by all browsers via `EventSource`.

**Connects to:** `OpenAICompatibleClient` (existing, extended with streaming), `RetrievalService` (existing, extended with `query_stream`), frontend (Phase 5 will consume the SSE endpoint).

---

## Step 3.5 — Tests

**File:** `tests/rag/test_retrieval.py` (extend)

| Test | What it verifies |
|---|---|
| `test_search_runs_concurrently` | Mock repos with different delays. Verify total time ≈ max delay, not sum. |
| `test_merge_scores_graph_discovery` | Graph returns chunk_id not in vector/FTS results. Verify it appears in final output. |
| `test_extract_snippet_sentence_boundary` | Verify snippet ends at sentence boundary, not mid-word. |
| `test_extract_snippet_short_text` | Text under 200 chars returned unchanged. |

**File:** `tests/api/test_streaming.py` (new)

| Test | What it verifies |
|---|---|
| `test_stream_endpoint_returns_sse` | POST `/query/stream`, verify `text/event-stream` content type. |
| `test_stream_emits_search_done_token_done` | Verify event sequence. |

**Connects to:** All step 3.1–3.4 changes.

---

# Phase 4 — Auth & User Scoping

## Abstract Overview

Add JWT-based authentication with email/password self-registration. Every resource becomes scoped to the authenticated user. This phase is foundational — the frontend (Phase 5) and observability (Phase 6) both assume auth exists.

## Final Objective

- Users register, login, receive JWT access (30 min) + refresh (7 day) token pairs
- All API endpoints require valid JWT (except `/health`, `/auth/login`, `/auth/register`)
- Every document, chunk, entity, relation is owned by a user via `user_id` FK
- Queries only search within the authenticated user's documents
- Refresh token rotation for security

---

## Step 4.1 — Dependencies

**File:** `backend/requirements.txt`

**Add:** `bcrypt>=4.1.0`, `PyJWT>=2.8.0`

**Why:** `bcrypt` for adaptive password hashing. `PyJWT` for stateless JWT creation/verification.

---

## Step 4.2 — User model

**File:** `backend/app/models/user.py` (new)

**New class:** `User(Base, TimestampMixin)`
- Table: `users`
- Columns: `id` (UUID PK), `email` (String 320, unique, indexed), `password_hash` (String 128), `is_active` (Boolean, default True)

**File:** `backend/app/models/__init__.py`

**Change:** Add `from backend.app.models.user import User`

---

## Step 4.3 — Migration: users table + user_id FKs

**File:** `backend/migrations/versions/0004_users_and_ownership.py` (new)

**`upgrade()`:**
1. Create `users` table
2. Add `user_id` (UUID, FK → `users.id`, NOT NULL, indexed) to: `documents`, `chunks`, `entities`, `relations`
3. Create indexes: `idx_documents_user_id`, `idx_chunks_user_id`, `idx_entities_user_id`

**`downgrade()`:** Drop columns and table in reverse order.

---

## Step 4.4 — Update existing ORM models

| File | Change |
|---|---|
| `backend/app/models/document.py` | Add `user_id: Mapped[UUID]` with `ForeignKey("users.id")` |
| `backend/app/models/chunk.py` | Add `user_id: Mapped[UUID]` with `ForeignKey("users.id")` |
| `backend/app/models/relation.py` | Add `user_id: Mapped[UUID]` to both `Entity` and `Relation` |

---

## Step 4.5 — Auth core

**File:** `backend/app/core/auth.py` (new)

| Function | Purpose |
|---|---|
| `hash_password(password: str) -> str` | `bcrypt.hashpw` + `gensalt` |
| `verify_password(plain: str, hashed: str) -> bool` | `bcrypt.checkpw` |
| `create_access_token(user_id: UUID, email: str, expires_minutes: int = 30) -> str` | JWT with `sub`, `email`, `exp`, `type: "access"` |
| `create_refresh_token(user_id: UUID, expires_days: int = 7) -> str` | JWT with `sub`, `exp`, `type: "refresh"` |
| `decode_token(token: str) -> dict` | `jwt.decode`, raises on invalid/expired |

**File:** `backend/app/config.py`

**Add to `Settings`:** `jwt_secret: str = Field(..., alias="JWT_SECRET")`, `jwt_access_token_expire_minutes: int = 30`, `jwt_refresh_token_expire_days: int = 7`

**File:** `.env.example` — add `JWT_SECRET=change-me-to-a-random-64-char-string`

---

## Step 4.6 — Auth dependency

**File:** `backend/app/dependencies.py`

**New function:** `async get_current_user(authorization: str = Header(...), session: AsyncSession = Depends(get_session)) -> User`

Extracts Bearer token → `decode_token()` → query `User` by ID → raise 401 if invalid/inactive.

---

## Step 4.7 — Scope repositories

| File | Method changes |
|---|---|
| `backend/repositories/document.py` | `create()` accepts `user_id`. `list()`, `get_by_id()`, `get_by_hash()`, `delete()` all add `.where(Document.user_id == user_id)`. |
| `backend/repositories/chunk.py` | `insert_many()` sets `user_id`. `search_vector()`, `search_fts()`, `get_by_document()` add `user_id` filter. |
| `backend/repositories/entity.py` | `insert_many()` sets `user_id`. `search_by_text()`, `get_by_document()` add `user_id` filter. |
| `backend/repositories/relation.py` | `insert_many()` sets `user_id`. `get_by_document()` adds `user_id` filter. |

---

## Step 4.8 — Auth API routes

**File:** `backend/schemas/auth.py` (new)

| Schema | Fields |
|---|---|
| `RegisterRequest` | `email: EmailStr`, `password: str` (min 8) |
| `LoginRequest` | `email: EmailStr`, `password: str` |
| `RefreshRequest` | `refresh_token: str` |
| `TokenResponse` | `access_token: str`, `refresh_token: str`, `token_type: str = "bearer"` |
| `UserResponse` | `id: UUID`, `email: str`, `created_at: datetime` |

**File:** `backend/app/api/auth.py` (new)

| Method | Path | Handler |
|---|---|---|
| POST | `/auth/register` | Create user, hash password, return tokens |
| POST | `/auth/login` | Verify credentials, return tokens |
| POST | `/auth/refresh` | Validate refresh token, issue new pair |
| GET | `/auth/me` | Return current user (requires `get_current_user`) |

**File:** `backend/app/api/router.py` — mount auth router.

---

## Step 4.9 — Scope existing route handlers

**File:** `backend/app/api/rag.py`

Every handler gets `user: User = Depends(get_current_user)` and passes `user.id` to repository/service calls.

**File:** `backend/rag/retrieval.py`

`query()` and `_search()` gain `user_id: UUID` parameter, passed through to all repository search calls.

**File:** `backend/rag/graph/service.py`

`search()`, `get_document_entities()`, `get_document_graph()` gain `user_id` parameter.

---

## Step 4.10 — Update ingestion pipeline for user ownership

**File:** `backend/rag/ingestion/pipeline.py`

**Change to `process()`:** Read `document.user_id` from the fetched document record. Pass `user_id` to `_embed_and_store()` and `_extract_and_store_graph()` so chunks, entities, and relations are created with the correct owner.

**File:** `backend/workers/jobs.py`

No change needed — the job function already fetches the document (which now has `user_id`) and the pipeline reads it.

---

## Step 4.11 — Tests

**File:** `tests/core/test_auth.py` (new) — 8 tests covering hashing, token creation/verification, expiry, invalid signatures.

**File:** `tests/api/test_auth.py` (new) — 10 tests covering register, login, refresh, me, duplicate email, weak password, wrong password, invalid token.

**File:** `tests/repositories/test_user_scoping.py` (new) — 6 tests verifying cross-user isolation for documents, chunks, entities.

**Files to update:** `tests/api/test_rag.py`, `tests/api/test_providers.py`, `tests/repositories/conftest.py`, `tests/rag/test_retrieval.py` — add `get_current_user` override, `sample_user` fixture, `user_id` params.

---

# Phase 5 — Frontend

## Abstract Overview

The React shell has all infrastructure (router, query client, API client, Tailwind, utilities) but zero application features. This phase builds the complete UI: auth pages, document management, query interface with streaming, and graph visualization.

## Final Objective

- Login/register pages with form validation
- Document upload with drag-and-drop and progress tracking
- Document list with status badges, pagination, delete
- Query interface with streaming answer display and citation highlights
- Graph visualization for document entities/relations
- Provider configuration settings panel

---

## Step 5.1 — Auth pages and token management

**File:** `frontend/src/api/auth.ts` (new)

Exports: `register()`, `login()`, `refresh()`, `getMe()`, `logout()`, `getTokens()`, `setTokens()`, `clearTokens()`

**File:** `frontend/src/api/client.ts`

**Change:** Add Axios request interceptor (attach `Authorization: Bearer <token>`). Add response interceptor (catch 401, attempt refresh, redirect to `/login` on failure).

**File:** `frontend/src/routes/login.tsx` (new) — email + password form, calls `login()`, stores tokens, redirects to `/`.

**File:** `frontend/src/routes/register.tsx` (new) — email + password + confirm form, calls `register()`, stores tokens, redirects to `/`.

**File:** `frontend/src/routes/__root.tsx`

**Change:** Add `beforeLoad` guard — check for token in storage, redirect to `/login` if absent (skip for `/login` and `/register` routes).

---

## Step 5.2 — Document upload page

**File:** `frontend/src/routes/documents/upload.tsx` (new)

**UI:** Drag-and-drop zone + file picker. Shows file name, size, extension validation before upload. Progress bar during upload. On success, redirects to document detail page.

**API call:** `POST /documents/upload` via `useMutation` from React Query.

**File:** `frontend/src/api/documents.ts` (new)

Exports: `uploadDocument(file, strategy)`, `listDocuments(limit, offset)`, `getDocument(id)`, `deleteDocument(id)`, `getDocumentChunks(id)`, `getDocumentGraph(id)`

---

## Step 5.3 — Document list page

**File:** `frontend/src/routes/documents/index.tsx` (new)

**UI:** Paginated table with columns: filename, file type, status (badge: queued/processing/completed/failed), chunk count, created date, actions (view, delete). Status auto-refreshes via React Query polling (5s interval for non-completed docs).

**API call:** `GET /documents` via `useQuery` with `refetchInterval` conditional on status.

---

## Step 5.4 — Document detail page

**File:** `frontend/src/routes/documents/$documentId.tsx` (new)

**UI:** Document metadata header. Tabs: Chunks (list of chunk text), Entities (list), Graph (interactive visualization). Delete button with confirmation.

**API calls:** `GET /documents/{id}`, `GET /documents/{id}/chunks`, `GET /documents/{id}/entities`, `GET /documents/{id}/graph` — all via `useQuery`.

---

## Step 5.5 — Graph visualization component

**File:** `frontend/src/components/GraphView.tsx` (new)

**UI:** Force-directed graph using SVG + d3-force (or a lightweight alternative like `react-force-graph` if bundle size is a concern). Nodes = entities (colored by type), edges = relations (labeled with relation_type). Interactive: drag nodes, zoom, pan, click for details.

**Props:** `entities: EntityResponse[]`, `relations: RelationResponse[]`

**Why SVG over Canvas:** The entity count per document is typically small (< 100 nodes). SVG gives better interactivity (DOM events per node) and accessibility at this scale.

---

## Step 5.6 — Query interface with streaming

**File:** `frontend/src/routes/query.tsx` (new)

**UI:** Chat-like interface. Text input at bottom. Answer streams in token-by-token. Citations shown below the answer as expandable cards (chunk text snippet, link to source document).

**Implementation:** Uses `fetch()` with `ReadableStream` to consume the SSE endpoint (`POST /query/stream`). Parses SSE events (`search_done`, `token`, `done`). Updates React state per event.

**Why `fetch` over Axios for streaming:** Axios doesn't support streaming responses natively. The native `fetch` API with `response.body.getReader()` is the standard approach for consuming SSE in React.

**File:** `frontend/src/api/query.ts` (new)

Exports: `queryStream(query, documentIds, top_k, onToken, onDone)` — wraps the fetch/SSE logic.

---

## Step 5.7 — Provider settings page

**File:** `frontend/src/routes/settings.tsx` (new)

**UI:** Shows current provider status (`GET /providers/status`). Form to configure provider: dropdown (OpenAI/DeepSeek), model name input, API key input (masked). Submit calls `POST /providers/configure`.

---

## Step 5.8 — Navigation and layout

**File:** `frontend/src/routes/__root.tsx`

**Change:** Add a sidebar/navbar with links: Home (query), Documents, Settings. Show logged-in user email. Logout button.

**File:** `frontend/src/routes/index.tsx`

**Change:** Replace static heading with a redirect to `/query` (or make the home page the query interface directly).

---

# Phase 6 — Observability & Error Handling

## Abstract Overview

Transform the API from "works locally" to "operable in production." Add structured logging, Prometheus metrics, and global exception handlers.

## Final Objective

- Every request logged with method, path, status, duration, user_id, request_id
- Prometheus metrics at `/metrics` (request count, latency histograms, LLM usage, ingestion jobs)
- Consistent JSON error responses via global exception handlers
- Custom exception hierarchy mapping domain errors to HTTP status codes
- Enhanced health endpoint with dependency checks

---

## Step 6.1 — structlog configuration

**File:** `backend/app/core/logging.py` (new)

**Functions:** `setup_logging(json_logs: bool)`, `get_logger(name: str) -> BoundLogger`

**File:** `backend/app/config.py` — add `json_logs: bool = True`

**File:** `backend/app/main.py` — call `setup_logging()` in `create_app()`

---

## Step 6.2 — Exception hierarchy and handlers

**File:** `backend/app/core/exceptions.py`

**Expand to:**
```
KnowMeshError (base) → NotFoundError (404), AuthenticationError (401),
AuthorizationError (403), ValidationError (422), LLMError (502),
IngestionError (500), RateLimitError (429)
```

**File:** `backend/app/core/error_handlers.py` (new)

**Function:** `register_exception_handlers(app)` — maps each exception to a JSON error response with appropriate status code. Logs via structlog.

**File:** `backend/app/main.py` — call `register_exception_handlers(app)`

---

## Step 6.3 — Request logging middleware

**File:** `backend/app/core/middleware.py` (new)

**Function:** `create_request_logging_middleware(app)` — generates request_id, binds structlog context, logs method/path/status/duration_ms/user_id, adds `X-Request-ID` header.

**File:** `backend/app/main.py` — register middleware in `create_app()`

---

## Step 6.4 — Prometheus metrics

**File:** `backend/requirements.txt` — add `prometheus-client>=0.20.0`

**File:** `backend/app/core/metrics.py` (new)

**Metrics:** `REQUEST_COUNT` (Counter), `REQUEST_LATENCY` (Histogram), `ACTIVE_REQUESTS` (Gauge), `LLM_REQUEST_COUNT` (Counter), `INGESTION_JOBS` (Counter).

**Function:** `create_metrics_middleware(app)` — increments counters per request.

**Route:** `GET /metrics` — returns Prometheus format.

**File:** `backend/app/main.py` — register middleware + route.

---

## Step 6.5 — Enhanced health endpoint

**File:** `backend/app/api/health.py`

**Change:** Add S3 check, uptime tracking, structured response with per-dependency status and latency. Return 503 on degraded.

---

## Step 6.6 — Instrument LLM calls

**File:** `backend/app/core/llm_manager.py`

**Change:** `embed()`, `rerank()`, `generate()`, `generate_stream()` increment `LLM_REQUEST_COUNT` and log duration.

**File:** `backend/workers/jobs.py`

**Change:** `process_document()` increments `INGESTION_JOBS` (success/failed) on completion.

---

## Step 6.7 — Tests

**File:** `tests/core/test_middleware.py` (new) — request logging, request_id header, metrics format.

**File:** `tests/core/test_error_handlers.py` (new) — each exception type maps to correct status code, response shape.

---

# Phase 7 — CI/CD & Test Expansion

## Abstract Overview

Add a GitHub Actions pipeline and expand test coverage to cover all new code from phases 1–6.

## Final Objective

- Every PR runs: lint, typecheck, tests (with coverage threshold), Docker build verification
- Coverage enforced at 80%
- All new modules have corresponding tests

---

## Step 7.1 — GitHub Actions workflow

**File:** `.github/workflows/ci.yml` (new)

**Jobs (parallel):**

| Job | Command |
|---|---|
| `lint` | `ruff check backend/` + `ruff format --check backend/` |
| `typecheck` | `mypy backend/` |
| `test` | `pytest tests/ -v --cov=backend --cov-report=term-missing --cov-fail-under=80` |
| `docker-build` | `docker compose -f docker-compose.yml -f docker-compose.dev.yml build` |

---

## Step 7.2 — Coverage configuration

**File:** `pyproject.toml`

**Add:**
```toml
[tool.coverage.run]
source = ["backend"]
omit = ["backend/migrations/*", "backend/workers/worker.py"]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = ["pragma: no cover", "if TYPE_CHECKING"]
```

---

## Step 7.3 — New test files (one per new module)

| New test file | Covers |
|---|---|
| `tests/rag/test_pipeline.py` | `IngestionPipeline` (Phase 1) |
| `tests/rag/test_extraction.py` | `EntityExtractor` (Phase 2) |
| `tests/api/test_upload.py` | Upload endpoint (Phase 1) |
| `tests/api/test_auth.py` | Auth routes (Phase 4) |
| `tests/api/test_streaming.py` | SSE endpoint (Phase 3) |
| `tests/core/test_auth.py` | JWT + bcrypt (Phase 4) |
| `tests/core/test_middleware.py` | Logging + metrics middleware (Phase 6) |
| `tests/core/test_error_handlers.py` | Exception handlers (Phase 6) |
| `tests/repositories/test_user_scoping.py` | Cross-user isolation (Phase 4) |

---

## Step 7.4 — Update existing tests

| File | Change |
|---|---|
| `tests/api/test_rag.py` | Add `get_current_user` dependency override |
| `tests/api/test_providers.py` | Same auth override |
| `tests/repositories/conftest.py` | Add `sample_user` fixture, update `sample_document` with `user_id` |
| `tests/rag/test_retrieval.py` | Add `user_id` param to mock calls |

---

## Phase Dependency Graph

```
Phase 1 (Ingestion)
  1.1 Schemas → 1.5 Upload endpoint
  1.2 Pipeline orchestrator → 1.3 Worker job → 1.4 Worker update
  1.6 Migration (s3_key) → 1.2
  1.7 DI wiring → 1.5
  1.8 Tests (after all above)

Phase 2 (Extraction) — requires Phase 1
  2.1 Prompt → 2.2 Extractor → 2.3 Pipeline integration → 2.4 DI → 2.5 Tests

Phase 3 (Query) — requires Phase 2 (graph populated)
  3.1 Concurrent search → 3.2 Graph discovery → 3.3 Citations → 3.4 Streaming → 3.5 Tests

Phase 4 (Auth) — requires Phase 3 (full API ready)
  4.1 Deps → 4.2 Model → 4.3 Migration → 4.4 Update models
  4.5 Auth core → 4.6 Auth dependency → 4.7 Scope repos → 4.8 Auth routes
  4.9 Scope handlers + 4.10 Pipeline ownership → 4.11 Tests

Phase 5 (Frontend) — requires Phase 4 (auth API exists)
  5.1 Auth pages → 5.2 Upload → 5.3 Doc list → 5.4 Doc detail → 5.5 Graph viz
  5.6 Query + streaming → 5.7 Settings → 5.8 Layout/nav

Phase 6 (Observability) — requires Phase 5 (all features exist)
  6.1 structlog → 6.2 Exceptions → 6.3 Logging middleware → 6.4 Metrics
  6.5 Health → 6.6 LLM instrumentation → 6.7 Tests

Phase 7 (CI/CD) — requires Phase 6 (all code written)
  7.1 Workflow → 7.2 Coverage config → 7.3 New tests → 7.4 Update existing
```
