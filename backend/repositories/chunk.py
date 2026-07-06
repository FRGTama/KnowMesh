from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.chunk import Chunk


class ChunkRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def insert_many(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        self._session.add_all(chunks)
        await self._session.commit()

    async def get_by_document(self, document_id: UUID) -> list[Chunk]:
        result = await self._session.execute(
            select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.index)
        )
        return list(result.scalars().all())

    async def delete_by_document(self, document_id: UUID) -> int:
        result = await self._session.execute(delete(Chunk).where(Chunk.document_id == document_id))
        await self._session.commit()
        return result.rowcount

    async def get_by_ids(self, chunk_ids: list[UUID]) -> list[Chunk]:
        if not chunk_ids:
            return []
        result = await self._session.execute(select(Chunk).where(Chunk.id.in_(chunk_ids)))
        return list(result.scalars().all())

    async def search_vector(
        self,
        query_embedding: list[float],
        top_k: int = 20,
        document_ids: list[UUID] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Cosine similarity search via pgvector. Returns (chunk, score) where score in [0, 1]."""
        distance_col = Chunk.embedding.cosine_distance(query_embedding).label("distance")
        stmt = select(Chunk, distance_col).where(Chunk.embedding.isnot(None)).order_by(distance_col).limit(top_k)
        if document_ids:
            stmt = stmt.where(Chunk.document_id.in_(document_ids))
        result = await self._session.execute(stmt)
        return [(row[0], max(0.0, 1.0 - row[1])) for row in result]

    async def search_fts(
        self,
        query_text: str,
        top_k: int = 20,
        document_ids: list[UUID] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Full-text search via ts_rank. Returns (chunk, raw_rank) — caller normalizes."""
        ts_vector = func.to_tsvector("english", Chunk.text)
        ts_query = func.plainto_tsquery("english", query_text)
        rank_col = func.ts_rank(ts_vector, ts_query).label("rank")
        stmt = select(Chunk, rank_col).where(ts_query.op("@@")(ts_vector)).order_by(rank_col.desc()).limit(top_k)
        if document_ids:
            stmt = stmt.where(Chunk.document_id.in_(document_ids))
        result = await self._session.execute(stmt)
        return [(row[0], float(row[1])) for row in result]
