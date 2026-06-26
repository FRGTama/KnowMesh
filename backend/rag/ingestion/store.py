from pathlib import Path

import chromadb
from chromadb.config import Settings

from backend.rag.ingestion.embedding import EmbeddedChunk


def _db_path() -> str:
    here = Path(__file__).resolve().parent.parent.parent.parent
    return str(here / "data" / "chroma")


class VectorStore:
    def __init__(self, collection_name: str = "student_rag"):
        path = _db_path()
        Path(path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))
        self._collection_name = collection_name
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: list[EmbeddedChunk]) -> None:
        if not chunks:
            return
        existing_ids = self._existing_ids({c.doc_id for c in chunks})
        to_add = [c for c in chunks if f"{c.doc_id}_{c.index}" not in existing_ids]
        if not to_add:
            return
        self._collection.add(
            ids=[f"{c.doc_id}_{c.index}" for c in to_add],
            embeddings=[c.vector for c in to_add],
            documents=[c.text for c in to_add],
            metadatas=[
                {
                    "document_id": c.metadata.get("document_id", ""),
                    "chunk_id": f"{c.doc_id}_{c.index}",
                    "index": c.index,
                    "page": c.metadata.get("page", 0),
                    "total_pages": c.metadata.get("total_pages", 0),
                    "strategy": c.strategy,
                    "filename": c.metadata.get("filename", ""),
                    "file_type": c.metadata.get("file_type", ""),
                }
                for c in to_add
            ],
        )

    def search(
        self,
        vector: list[float],
        top_k: int = 5,
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        if not vector or all(v == 0.0 for v in vector):
            return []

        where = None
        if document_ids:
            where = {"document_id": {"$in": document_ids}}

        results = self._collection.query(
            query_embeddings=[vector],
            n_results=top_k,
            where=where,
        )
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        return formatted

    def count(self) -> int:
        return self._collection.count()

    def clear(self) -> int:
        count = self._collection.count()
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        return count

    def delete_by_document_id(self, document_id: str) -> int:
        existing = self._collection.get(
            where={"document_id": document_id},
            include=[],
        )
        ids = existing["ids"]
        if not ids:
            return 0
        self._collection.delete(ids=ids)
        return len(ids)

    def _existing_ids(self, doc_ids: set[str]) -> set[str]:
        if not doc_ids:
            return set()
        try:
            result = self._collection.get(
                where={"document_id": {"$in": list(doc_ids)}},
                include=[],
            )
            return set(result["ids"])
        except Exception:
            return set()
