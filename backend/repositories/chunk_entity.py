from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.chunk_entity import ChunkEntity


class ChunkEntityRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def insert_many(self, links: list[ChunkEntity]) -> None:
        if not links:
            return
        self._session.add_all(links)
        await self._session.commit()

    async def get_by_chunk(self, chunk_id: UUID) -> list[ChunkEntity]:
        result = await self._session.execute(
            select(ChunkEntity).where(ChunkEntity.chunk_id == chunk_id)
        )
        return list(result.scalars().all())

    async def get_by_entity(self, entity_id: UUID) -> list[ChunkEntity]:
        result = await self._session.execute(
            select(ChunkEntity).where(ChunkEntity.entity_id == entity_id)
        )
        return list(result.scalars().all())

    async def get_chunks_for_entities(self, entity_ids: list[UUID]) -> list[tuple[UUID, int]]:
        """Return (chunk_id, match_count) for chunks linked to any of the given entities."""
        if not entity_ids:
            return []
        result = await self._session.execute(
            select(ChunkEntity.chunk_id, func.count().label("cnt"))
            .where(ChunkEntity.entity_id.in_(entity_ids))
            .group_by(ChunkEntity.chunk_id)
            .order_by(func.count().desc())
        )
        return [(row[0], row[1]) for row in result]

    async def delete_by_chunk(self, chunk_id: UUID) -> int:
        from sqlalchemy import delete

        result = await self._session.execute(
            delete(ChunkEntity).where(ChunkEntity.chunk_id == chunk_id)
        )
        await self._session.commit()
        return result.rowcount
