# KnowMesh — Implementation Checklist

## Phase 1 — Ingestion Pipeline

- [ ] **1.1** Add `UploadResponse` schema to `backend/schemas/document.py`
- [ ] **1.1** Add `user_id: UUID | None = None` to `DocumentCreate`
- [ ] **1.2** Create `backend/rag/ingestion/pipeline.py` with `IngestionPipeline` class
- [ ] **1.2** Implement `process()`, `_download()`, `_parse()`, `_chunk()`, `_embed_and_store()`, `_update_status()`
- [ ] **1.3** Create `backend/workers/jobs.py` with `process_document()` function
- [ ] **1.3** Bridge async pipeline from sync RQ worker via `asyncio.run()`
- [ ] **1.4** Update `backend/workers/worker.py` to import `backend.workers.jobs`
- [ ] **1.5** Add `POST /documents/upload` handler to `backend/app/api/rag.py`
- [ ] **1.5** Implement file validation (extension, size), SHA-256 hash, dedup check
- [ ] **1.5** Wire S3 upload + Document creation + RQ enqueue
- [ ] **1.6** Add `s3_key` column to `backend/app/models/document.py`
- [ ] **1.6** Create migration `backend/migrations/versions/0003_document_s3_key.py`
- [ ] **1.7** Add `get_ingestion_pipeline()` to `backend/app/dependencies.py`
- [ ] **1.8** Create `tests/rag/test_pipeline.py` (4 tests: happy path, failure, batching, empty)
- [ ] **1.8** Create `tests/api/test_upload.py` (4 tests: success, bad ext, size limit, dedup)

## Phase 2 — Entity Extraction

- [ ] **2.1** Create `backend/prompts/system/entity_extractor.md` with NER prompt
- [ ] **2.2** Create `backend/rag/extraction.py` with `ExtractedGraph` dataclass and `EntityExtractor` class
- [ ] **2.2** Implement `extract()` and `_parse_response()` with markdown-fence JSON fallback
- [ ] **2.3** Add `graph_service` and `extractor` params to `IngestionPipeline.__init__()`
- [ ] **2.3** Implement `_extract_and_store_graph()` with `asyncio.gather` + semaphore=5
- [ ] **2.3** Wire extraction into `process()` flow (after `_embed_and_store`)
- [ ] **2.3** Implement entity deduplication by normalized name
- [ ] **2.4** Update `get_ingestion_pipeline()` in `dependencies.py` to pass `GraphService` + `EntityExtractor`
- [ ] **2.5** Create `tests/rag/test_extraction.py` (4 tests: valid JSON, markdown wrap, malformed, empty)
- [ ] **2.5** Extend `tests/rag/test_pipeline.py` (3 tests: with extraction, failure continues, no extractor skips)

## Phase 3 — Query Path Hardening

- [ ] **3.1** Replace sequential awaits in `RetrievalService._search()` with `asyncio.gather()`
- [ ] **3.2** Add `document_ids` param to `GraphService.search()` and `EntityRepository.search_by_text()`
- [ ] **3.2** Make `_merge_scores()` async, allow graph discovery of chunks not found by vector/FTS
- [ ] **3.2** Add post-merge `get_by_ids()` fetch for graph-discovered chunks missing from `chunk_map`
- [ ] **3.3** Add `_extract_snippet()` static method with sentence-boundary truncation
- [ ] **3.3** Replace `c.text[:200]` with `self._extract_snippet(c.text)` in `query()`
- [ ] **3.4** Add `generate_stream()` to `GenerateClient` Protocol and `OpenAICompatibleClient`
- [ ] **3.4** Add `generate_stream()` to `LLMManager`
- [ ] **3.4** Add `generate_stream()` to `Generator`
- [ ] **3.4** Add `query_stream()` to `RetrievalService` yielding SSE events
- [ ] **3.4** Add `POST /query/stream` route handler with `StreamingResponse`
- [ ] **3.5** Extend `tests/rag/test_retrieval.py` (4 tests: concurrency, graph discovery, snippet boundary, short text)
- [ ] **3.5** Create `tests/api/test_streaming.py` (2 tests: SSE content type, event sequence)

## Phase 4 — Auth & User Scoping

- [ ] **4.1** Add `bcrypt>=4.1.0` and `PyJWT>=2.8.0` to `backend/requirements.txt`
- [ ] **4.2** Create `backend/app/models/user.py` with `User` model
- [ ] **4.2** Add `User` re-export to `backend/app/models/__init__.py`
- [ ] **4.3** Create migration `0004_users_and_ownership.py` (users table + user_id FKs on all resource tables)
- [ ] **4.4** Add `user_id` column to `Document`, `Chunk`, `Entity`, `Relation` ORM models
- [ ] **4.5** Create `backend/app/core/auth.py` with `hash_password()`, `verify_password()`, `create_access_token()`, `create_refresh_token()`, `decode_token()`
- [ ] **4.5** Add `jwt_secret`, `jwt_access_token_expire_minutes`, `jwt_refresh_token_expire_days` to `Settings`
- [ ] **4.5** Add `JWT_SECRET` to `.env.example`
- [ ] **4.6** Add `get_current_user()` dependency to `backend/app/dependencies.py`
- [ ] **4.7** Add `user_id` filter to all methods in `DocumentRepository`
- [ ] **4.7** Add `user_id` filter to all methods in `ChunkRepository`
- [ ] **4.7** Add `user_id` filter to all methods in `EntityRepository`
- [ ] **4.7** Add `user_id` filter to all methods in `RelationRepository`
- [ ] **4.8** Create `backend/schemas/auth.py` (RegisterRequest, LoginRequest, RefreshRequest, TokenResponse, UserResponse)
- [ ] **4.8** Create `backend/app/api/auth.py` with register, login, refresh, me endpoints
- [ ] **4.8** Mount auth router in `backend/app/api/router.py`
- [ ] **4.9** Add `get_current_user` dependency to all handlers in `backend/app/api/rag.py`
- [ ] **4.9** Add `user_id` param to `RetrievalService.query()` and `_search()`
- [ ] **4.9** Add `user_id` param to `GraphService.search()`, `get_document_entities()`, `get_document_graph()`
- [ ] **4.10** Update `IngestionPipeline.process()` to read and propagate `document.user_id`
- [ ] **4.11** Create `tests/core/test_auth.py` (8 tests)
- [ ] **4.11** Create `tests/api/test_auth.py` (10 tests)
- [ ] **4.11** Create `tests/repositories/test_user_scoping.py` (6 tests)
- [ ] **4.11** Update existing tests: `test_rag.py`, `test_providers.py`, `conftest.py`, `test_retrieval.py`

## Phase 5 — Frontend

- [ ] **5.1** Create `frontend/src/api/auth.ts` with register, login, refresh, getMe, logout, token helpers
- [ ] **5.1** Add request/response interceptors to `frontend/src/api/client.ts`
- [ ] **5.1** Create `frontend/src/routes/login.tsx`
- [ ] **5.1** Create `frontend/src/routes/register.tsx`
- [ ] **5.1** Add `beforeLoad` auth guard to `frontend/src/routes/__root.tsx`
- [ ] **5.2** Create `frontend/src/api/documents.ts` with all document API functions
- [ ] **5.2** Create `frontend/src/routes/documents/upload.tsx` with drag-and-drop + progress
- [ ] **5.3** Create `frontend/src/routes/documents/index.tsx` with paginated table + status polling
- [ ] **5.4** Create `frontend/src/routes/documents/$documentId.tsx` with tabs (chunks, entities, graph)
- [ ] **5.5** Create `frontend/src/components/GraphView.tsx` with force-directed SVG graph
- [ ] **5.6** Create `frontend/src/api/query.ts` with SSE stream consumer
- [ ] **5.6** Create `frontend/src/routes/query.tsx` with streaming answer display + citations
- [ ] **5.7** Create `frontend/src/routes/settings.tsx` with provider config form
- [ ] **5.8** Add sidebar/navbar to `__root.tsx` with nav links + user email + logout
- [ ] **5.8** Update `index.tsx` to redirect to `/query`

## Phase 6 — Observability & Error Handling

- [ ] **6.1** Create `backend/app/core/logging.py` with `setup_logging()` and `get_logger()`
- [ ] **6.1** Add `json_logs: bool = True` to `Settings`
- [ ] **6.1** Call `setup_logging()` in `create_app()`
- [ ] **6.2** Expand `backend/app/core/exceptions.py` with full hierarchy (KnowMeshError, NotFoundError, AuthenticationError, AuthorizationError, ValidationError, IngestionError, RateLimitError)
- [ ] **6.2** Create `backend/app/core/error_handlers.py` with `register_exception_handlers()`
- [ ] **6.2** Call `register_exception_handlers(app)` in `create_app()`
- [ ] **6.3** Create `backend/app/core/middleware.py` with `create_request_logging_middleware()`
- [ ] **6.3** Register middleware in `create_app()`
- [ ] **6.4** Add `prometheus-client>=0.20.0` to `backend/requirements.txt`
- [ ] **6.4** Create `backend/app/core/metrics.py` with counters, histograms, gauge
- [ ] **6.4** Add `create_metrics_middleware()` and `GET /metrics` route
- [ ] **6.5** Enhance `backend/app/api/health.py` with S3 check, uptime, structured response, 503 on degraded
- [ ] **6.6** Instrument `LLMManager` methods with `LLM_REQUEST_COUNT` + duration logging
- [ ] **6.6** Instrument `process_document()` with `INGESTION_JOBS` counter
- [ ] **6.7** Create `tests/core/test_middleware.py` (request logging, request_id, metrics)
- [ ] **6.7** Create `tests/core/test_error_handlers.py` (exception to status code mapping)

## Phase 7 — CI/CD & Test Expansion

- [ ] **7.1** Create `.github/workflows/ci.yml` with lint, typecheck, test, docker-build jobs
- [ ] **7.2** Add `[tool.coverage.run]` and `[tool.coverage.report]` to `pyproject.toml` (fail_under=80)
- [ ] **7.3** Verify all 9 new test files exist from phases 1-6
- [ ] **7.4** Update `tests/api/test_rag.py` with `get_current_user` override
- [ ] **7.4** Update `tests/api/test_providers.py` with auth override
- [ ] **7.4** Update `tests/repositories/conftest.py` with `sample_user` fixture + `user_id` on `sample_document`
- [ ] **7.4** Update `tests/rag/test_retrieval.py` with `user_id` params
