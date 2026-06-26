# KnowMesh — Student RAG Assistant

A FastAPI-based Retrieval-Augmented Generation system for students. Upload study materials, chunk & embed them, then ask questions against your personal knowledge base.

## Quick Start

```bash
pip install -r requirements.txt
uvicorn frontend.app:app
# Open http://localhost:8000
```

Set API keys (optional — provider can be set to "none" for stub responses):

```bash
export OPENAI_API_KEY="sk-..."
export DEEPSEEK_API_KEY="sk-..."
```

## Architecture

```
Upload (.txt / .pdf) → Document Loader → Chunker → Embedder → ChromaDB (persistent)
                                                                    ↓
Query → Embed query → ChromaDB search → Context assembly → LLM (OpenAI / DeepSeek) → Answer
```

## Project Structure

```
KnowMesh/
├── backend/
│   ├── llm.py                              # Embedding + LLM provider clients
│   └── rag/
│       ├── agents/
│       │   └── retrieval_agent.py          # Orchestrates query → context → answer
│       ├── graph/
│       │   └── __init__.py                 # Placeholder: temporal knowledge graph
│       └── ingestion/
│           ├── __init__.py
│           ├── chunking.py                 # RecursiveChunker, SemanticChunker
│           ├── document_loader.py          # .txt + .pdf loaders
│           ├── embedding.py                # Chunk → vector embedding
│           ├── pipeline.py                 # process_file, process_query, clear, count
│           └── store.py                    # ChromaDB persistent client
├── frontend/
│   ├── app.py                              # FastAPI routes
│   └── templates/
│       └── index.html                      # Upload, query, clear UI
├── knowmesh/data/chroma/                   # Persistent vector DB (auto-created)
├── requirements.txt
└── README.md
```

## Features

- **File formats**: `.txt` and `.pdf` (one page = one document node)
- **Chunking strategies**: Recursive (token-window) or Semantic (paragraph-boundary, falls back to recursive on long paragraphs)
- **Vector store**: ChromaDB with cosine similarity, persisted to disk
- **LLM providers**: OpenAI (`gpt-4o`), DeepSeek (`deepseek-v4-pro`), or stub (no API key needed)
- **Database management**: Clear all vectors with a single button (with confirmation dialog showing collection name + document count)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Main page |
| POST | `/upload` | Upload a file (form: `file`, `strategy`) |
| POST | `/query` | Ask a question (form: `query`, `provider`) |
| GET | `/collection-info` | JSON `{name, count}` |
| POST | `/clear` | Delete all vectors, returns `{cleared, count}` |

## Limitations (MVP)

- No document deletion (only full clear)
- No authentication or multi-user
- Single collection
- No hybrid search (vector-only)
