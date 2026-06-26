# KnowMesh — Student RAG Assistant

A FastAPI + React Retrieval-Augmented Generation system for students. Upload study materials (PDF, DOCX, PPTX, images, plain text), chunk & embed them, then ask questions against your personal knowledge base with your choice of LLM provider.

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
  → LiteParse (local Rust parser) → pages
  → TextLoader (.txt) → raw text
        ↓
   Document (text + metadata)
        ↓
   BaseChunker (Recursive | Semantic)
        ↓
   EmbeddedChunk (text + vector)
        ↓
   ChromaDB PersistentClient (disk)
        ↓                    ↑
   Query → embed query → search → context assembly → LLM (OpenAI / DeepSeek) → Answer
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
│       │   └── __init__.py                 # Placeholder: temporal knowledge graph
│       └── ingestion/
│           ├── __init__.py
│           ├── chunking.py                 # RecursiveChunker, SemanticChunker
│           ├── document_loader.py          # SOLID: ABC + LoaderRegistry (TextLoader, LiteParseLoader)
│           ├── embedding.py                # Chunk → vector embedding
│           ├── pipeline.py                 # process_file, process_query, clear, count
│           └── store.py                    # ChromaDB PersistentClient
├── frontend/
│   ├── app.py                              # FastAPI routes (JSON API + static SPA)
│   ├── package.json                        # Vite + React
│   ├── vite.config.js                      # Dev proxy to FastAPI
│   ├── index.html                          # SPA entry
│   ├── src/
│   │   ├── main.jsx                        # React mount
│   │   ├── App.jsx                         # State orchestration + UI components
│   │   ├── App.css                         # Styles
│   │   └── api.js                          # Fetch wrappers for all endpoints
│   └── dist/                               # Production build (auto-generated)
├── data/chroma/                            # Persistent vector DB (auto-created)
├── requirements.txt
└── README.md
```

## Features

- **File formats**: `.txt`, `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.png`, `.jpg`, `.jpeg`
  - Parsed by [LiteParse](https://github.com/run-llama/liteparse) (local Rust engine, no API keys)
  - PDF via PDFium, Office formats via LibreOffice, images via Tesseract OCR
- **Chunking strategies**: Recursive (token-window) or Semantic (paragraph-boundary, falls back to recursive on long paragraphs)
- **Vector store**: ChromaDB with cosine similarity, persisted to disk
- **LLM providers**: OpenAI (`gpt-4o`), DeepSeek (`deepseek-v4-flash`), or stub (no API key needed)
- **Embedding model**: `all-MiniLM-L6-v2` via SentenceTransformers (loaded once, cached globally)
- **Database management**: Clear all vectors with a single button (with confirmation dialog showing collection name + document count)
- **React SPA**: FastAPI serves a built React app in production; Vite dev server with HMR in development

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/upload` | Upload a file (form: `file`, `strategy`) → `{ok, filename}` |
| POST | `/query` | Ask a question (form: `query`, `provider`) → `{answer}` |
| GET | `/collection-info` | `{name, count}` |
| POST | `/clear` | Delete all vectors → `{cleared, count}` |

## SOLID Design (document_loader.py)

| Principle | Implementation |
|-----------|----------------|
| **SRP** | `TextLoader` handles `.txt`, `LiteParseLoader` handles binary formats |
| **OCP** | New format = new `DocumentLoader` subclass + `registry.register()` — no existing code changes |
| **LSP** | All loaders conform to `DocumentLoader` ABC |
| **ISP** | Minimal interface: `load(path, base_metadata) → list[Document]` |
| **DIP** | `load()` depends on `LoaderRegistry` and `DocumentLoader` ABC, never on concrete parsers |

## Limitations (MVP)

- No document deletion (only full clear)
- No authentication or multi-user
- Single collection
- No hybrid search (vector-only)
