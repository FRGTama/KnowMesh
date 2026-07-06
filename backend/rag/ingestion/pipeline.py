import asyncio
import tempfile
import uuid
from pathlib import Path

import tiktoken

from backend.app.core.s3 import S3Client
from backend.app.models.chunk import Chunk as OrmChunk
from backend.rag.embedding import Embedder
from backend.rag.ingestion.chunking import BaseChunker, Chunk
from backend.rag.ingestion.document_loader import Document, LoaderRegistry, load
from backend.repositories.chunk import ChunkRepository
from backend.repositories.document import DocumentRepository
from backend.schemas.document import DocumentUpdate

_ENCODING = tiktoken.get_encoding("cl100k_base")


class IngestionPipeline:
    def __init__(
        self,
        s3: S3Client,
        chunk_repo: ChunkRepository,
        document_repo: DocumentRepository,
        embedder: Embedder,
        loader_registry: LoaderRegistry,
        chunker: BaseChunker,
        embed_batch_size: int = 96,
    ):
        self._s3 = s3
        self._chunk_repo = chunk_repo
        self._document_repo = document_repo
        self._embedder = embedder
        self._loader_registry = loader_registry
        self._chunker = chunker
        self._embed_batch_size = embed_batch_size

    async def process(self, document_id: uuid.UUID) -> None:
        doc = await self._document_repo.get_by_id(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        await self._update_status(document_id, "processing")

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir) / doc.filename
                await self._download(doc.s3_key, tmp_path)
                pages = self._parse(tmp_path, document_id)
                chunks = self._chunk(pages)
                count = await self._embed_and_store(chunks, document_id)
                await self._update_status(document_id, "completed", chunk_count=count)
        except Exception as e:
            await self._update_status(document_id, "failed", error=str(e))
            raise

    async def _download(self, s3_key: str, dest: Path) -> Path:
        return await self._s3.download(s3_key, dest)

    def _parse(self, path: Path, document_id: uuid.UUID) -> list[Document]:
        return load(str(path), document_id=str(document_id), registry=self._loader_registry)

    def _chunk(self, documents: list[Document]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for doc in documents:
            chunks.extend(self._chunker.chunk(doc))
        return chunks

    async def _embed_and_store(self, chunks: list[Chunk], document_id: uuid.UUID) -> int:
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        embeddings: list[list[float]] = []
        for i in range(0, len(texts), self._embed_batch_size):
            batch = texts[i : i + self._embed_batch_size]
            batch_embeddings = await self._embedder.embed(batch)
            embeddings.extend(batch_embeddings)
            if i + self._embed_batch_size < len(texts):
                await asyncio.sleep(0.1)

        orm_chunks: list[OrmChunk] = []
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            orm_chunks.append(
                OrmChunk(
                    id=uuid.uuid4(),
                    document_id=document_id,
                    index=chunk.index,
                    text=chunk.text,
                    embedding=embedding,
                    page=chunk.metadata.get("page", 0),
                    total_pages=chunk.metadata.get("total_pages", 0),
                    strategy=chunk.strategy,
                    tokens=len(_ENCODING.encode(chunk.text)),
                )
            )

        await self._chunk_repo.insert_many(orm_chunks)
        return len(orm_chunks)

    async def _update_status(
        self,
        document_id: uuid.UUID,
        status: str,
        error: str | None = None,
        chunk_count: int | None = None,
    ) -> None:
        update = DocumentUpdate(status=status, error=error, chunk_count=chunk_count)
        await self._document_repo.update(document_id, update)
