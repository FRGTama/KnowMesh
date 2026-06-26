import uuid
from pathlib import Path

from backend.llm import embed as _embed_query
from backend.rag.ingestion.chunking import BaseChunker, RecursiveChunker, SemanticChunker
from backend.rag.ingestion.document_loader import load as _load
from backend.rag.ingestion.embedding import embed_chunks as _embed_chunks
from backend.rag.ingestion.store import VectorStore
from backend.rag.registry import DocumentRecord, DocumentRegistry, FileStorage


class Pipeline:
    def __init__(
        self,
        registry: DocumentRegistry,
        storage: FileStorage,
        store: VectorStore | None = None,
    ):
        self._registry = registry
        self._storage = storage
        self._store = store or VectorStore()

    def process_file(
        self,
        path: str,
        strategy: str = "recursive",
        tags: list[str] | None = None,
    ) -> str:
        path_obj = Path(path)
        content = path_obj.read_bytes()
        document_id = uuid.uuid4().hex
        filename = path_obj.name
        file_type = path_obj.suffix.lower()

        source_path = self._storage.save(document_id, filename, content)

        self._registry.create_document(DocumentRecord(
            id=document_id,
            filename=filename,
            source_path=source_path,
            file_type=file_type,
            status="processing",
            tags=tags or [],
        ))

        try:
            documents = _load(path, document_id=document_id)
            chunker = _resolve_chunker(strategy)
            total_pages = 0
            all_chunks = []
            for doc in documents:
                if doc.metadata.get("error"):
                    continue
                for chunk in chunker.chunk(doc):
                    chunk.index = len(all_chunks)
                    all_chunks.append(chunk)
                total_pages = max(total_pages, doc.metadata.get("total_pages", 0))

            embedded = _embed_chunks(all_chunks)
            self._store.upsert(embedded)

            self._registry.update_document(
                document_id,
                status="completed",
                chunk_count=len(embedded),
                total_pages=total_pages,
                strategy=strategy,
            )
        except Exception as e:
            self._registry.update_document(
                document_id,
                status="failed",
                error=str(e),
            )
            raise

        return document_id

    def process_query(
        self,
        query: str,
        top_k: int = 5,
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        query_vector = _embed_query(query)
        return self._store.search(query_vector, top_k, document_ids=document_ids)

    def count_store(self) -> int:
        return self._store.count()

    def clear_store(self) -> int:
        count = self._store.clear()
        for doc in self._registry.list_documents():
            self._storage.delete(doc.id)
            self._registry.delete_document(doc.id)
        return count

    def delete_document(self, document_id: str) -> int:
        chunk_count = self._store.delete_by_document_id(document_id)
        self._storage.delete(document_id)
        self._registry.delete_document(document_id)
        return chunk_count

    def list_documents(self) -> list[DocumentRecord]:
        return self._registry.list_documents()

    def get_document(self, document_id: str) -> DocumentRecord | None:
        return self._registry.get_document(document_id)


def _resolve_chunker(strategy: str) -> BaseChunker:
    if strategy == "semantic":
        return SemanticChunker()
    return RecursiveChunker()
