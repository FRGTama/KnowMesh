from backend.rag.ingestion.document_loader import load as _load
from backend.rag.ingestion.chunking import BaseChunker, RecursiveChunker, SemanticChunker
from backend.rag.ingestion.embedding import embed_chunks as _embed_chunks
from backend.rag.ingestion.store import VectorStore
from backend.llm import embed as _embed_query


_vector_store = None


def _get_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def process_file(path: str, strategy: str = "recursive") -> None:
    documents = _load(path)
    chunker = _resolve_chunker(strategy)
    store = _get_store()
    for doc in documents:
        chunks = chunker.chunk(doc)
        embedded = _embed_chunks(chunks)
        store.upsert(embedded)


def process_query(query: str, top_k: int = 5) -> list[dict]:
    query_vector = _embed_query(query)
    return _get_store().search(query_vector, top_k)


def _resolve_chunker(strategy: str) -> BaseChunker:
    if strategy == "semantic":
        return SemanticChunker()
    return RecursiveChunker()
