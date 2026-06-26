# KnowMesh — Student RAG Assistant

A FastAPI + React Retrieval-Augmented Generation system for students. Upload study materials (PDF, DOCX, PPTX, images, plain text), chunk & embed them, then ask questions against your personal knowledge base with your choice of LLM provider.

## TODO
Backend:
- [] Chunk storing id should change to using UUID to be unique
- [] Task queue for async jobs
- [] Duplication checking, updating old document to newer
- [] keyword + semantic search (hybrid search)
Frontend:
- [] Document list, actions: delete, view, move(future)

## Quick Start

```bash
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
uvicorn frontend.app:app
# Open http://localhost:8000
```

Set API keys (optional — provider can be set to "none" for stub responses):

```bash
export OPENAI_API_KEY="sk-..."
export DEEPSEEK_API_KEY="sk-..."
```

### Development

```bash
# Terminal 1 — FastAPI backend
uvicorn frontend.app:app --reload

# Terminal 2 — Vite dev server (HMR)
cd frontend && npm run dev
# Open http://localhost:5173
```

## Architecture

```
Upload (any format)
  → LiteParse / TextLoader → paged documents
  → Chunker (Recursive | Semantic)
  → EmbeddedChunk (text + vector + document_id)
  → VectorStore (ChromaDB) + DocumentRegistry (SQLite)
        ↓
  Query → embed → search (optionally filtered by document_ids)
  → context assembly → LLM (OpenAI / DeepSeek) → Answer
```

## Project Structure

```
KnowMesh/
├── backend/
│   ├── llm.py                              # Embedding model (cached) + LLM providers
│   └── rag/
│       ├── agents/
│       │   └── retrieval_agent.py          # Orchestrates query → context → answer
│       ├── graph/
│       │   └── __init__.py                 # Placeholder
│       ├── registry/                       # Document tracking system
│       │   ├── __init__.py
│       │   ├── interface.py               # DocumentRegistry ABC
│       │   ├── models.py                  # DocumentRecord dataclass
│       │   ├── sqlite_registry.py         # SQLite implementation
│       │   └── file_storage.py            # Persistent file I/O
│       └── ingestion/
│           ├── __init__.py
│           ├── chunking.py                # RecursiveChunker, SemanticChunker
│           ├── document_loader.py         # SOLID: ABC + LoaderRegistry
│           ├── embedding.py               # Chunk → vector
│           ├── pipeline.py                # Pipeline orchestrator (injectable deps)
│           └── store.py                   # ChromaDB with doc-level operations
├── frontend/
│   ├── app.py                             # FastAPI routes (JSON API + static SPA)
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── src/
│   │   ├── config.js                      # PROVIDER_MODELS constant
│   │   ├── api.js
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── components/
│   │       ├── UploadForm.jsx
│   │       ├── QueryForm.jsx
│   │       ├── ClearDatabase.jsx
│   │       ├── AnswerDisplay.jsx
│   │       └── FlashMessage.jsx
│   └── dist/
├── data/
│   ├── chroma/                            # Vector DB (auto-created)
│   ├── registry.db                        # Document registry (SQLite, auto-created)
│   └── storage/                           # Uploaded files by document_id
├── requirements.txt
└── README.md
```

## Features

- **File formats**: `.txt`, `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.png`, `.jpg`, `.jpeg`
  - Parsed by [LiteParse](https://github.com/run-llama/liteparse) (local Rust engine, no API keys)
- **Chunking strategies**: Recursive (token-window) or Semantic (paragraph-boundary)
- **Vector store**: ChromaDB with cosine similarity, persisted to disk
- **Document registry**: SQLite-backed tracking per document (status, chunk count, tags)
- **Persistent file storage**: Uploaded files saved to `data/storage/{document_id}/`
- **Document-level operations**: List, get, delete individual documents and their chunks
- **Query filtering**: Search within specific documents by document_id
- **LLM providers**: OpenAI (`gpt-4o`), DeepSeek (`deepseek-v4-flash`), or stub (no API key)
- **Model selection**: Per-provider model dropdown, disabled until provider selected
- **Embedding model**: `all-MiniLM-L6-v2` (loaded once, cached globally)
- **React SPA**: FastAPI serves built React app; Vite dev server with HMR in development

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/upload` | Upload a file (form: `file`, `strategy`) → `{ok, filename, document_id}` |
| POST | `/query` | Ask (form: `query`, `provider`, `model`, `document_ids?`) → `{answer}` |
| GET | `/documents` | List all tracked documents |
| GET | `/documents/{id}` | Get document details |
| DELETE | `/documents/{id}` | Delete document + chunks + file |
| GET | `/collection-info` | `{name, count}` |
| POST | `/clear` | Delete all documents + chunks → `{cleared, count}` |

## SOLID Design

### document_loader.py

| Principle | Implementation |
|-----------|----------------|
| **SRP** | `TextLoader` handles `.txt`, `LiteParseLoader` handles binary formats |
| **OCP** | New format = new `DocumentLoader` subclass + registry.register() |
| **LSP** | All loaders conform to `DocumentLoader` ABC |
| **ISP** | Minimal interface: `load(path, base_metadata) → list[Document]` |
| **DIP** | `load()` depends on `LoaderRegistry` and `DocumentLoader` ABC |

### registry/

| Principle | Implementation |
|-----------|----------------|
| **SRP** | `SqliteRegistry` tracks metadata, `FileStorage` handles files, `models` defines schema |
| **OCP** | New backend (PostgreSQL, etc.) = implement `DocumentRegistry` ABC |
| **LSP** | All registry implementations interchangeable |
| **ISP** | `DocumentRegistry` has focused methods: create/get/list/update/delete |
| **DIP** | `Pipeline` depends on `DocumentRegistry` ABC + `FileStorage`, not on SQLite directly |

### pipeline.py

| Principle | Implementation |
|-----------|----------------|
| **SRP** | `Pipeline` orchestrates ingest/query/delete lifecycle |
| **DIP** | Accepts `DocumentRegistry`, `FileStorage`, `VectorStore` via constructor injection |

## Chunk Metadata (VectorStore)

Each chunk stored in ChromaDB carries:

```json
{
  "document_id": "uuid-hex",
  "chunk_id": "uuid-hex_chunk_0",
  "index": 0,
  "page": 0,
  "total_pages": 5,
  "strategy": "recursive",
  "filename": "report.pdf",
  "file_type": ".pdf"
}
```

## Data Flow

```
POST /upload
  → Pipeline.process_file()
    → registry.create(status="processing")
    → file_storage.save(document_id, file)
    → load → chunk → embed → store.upsert()
    → registry.update(status="completed", chunk_count=N)
  → return document_id

POST /query { document_ids: ["id1"] }
  → Pipeline.process_query(document_ids=["id1"])
    → store.search(where={"document_id": {"$in": ["id1"]}})
    → generate_response()

DELETE /documents/{id}
  → Pipeline.delete_document(id)
    → store.delete_by_document_id(id)
    → file_storage.delete(id)
    → registry.delete(id)
  → return {chunk_count}
```

## Limitations (MVP)

- No authentication or multi-user
- Single ChromaDB collection
- No hybrid search (vector-only)
- No re-ingestion of updated files
