from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.relation import Relation


class RelationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def insert_many(self, relations: list[Relation]) -> None:
        if not relations:
            return
        self._session.add_all(relations)
        await self._session.commit()

    async def get_for_entities(self, entity_ids: list[UUID]) -> list[Relation]:
        if not entity_ids:
            return []
        result = await self._session.execute(
            select(Relation).where(
                (Relation.source_entity_id.in_(entity_ids)) | (Relation.target_entity_id.in_(entity_ids))
            )
        )
        return list(result.scalars().all())

    async def get_by_document(self, document_id: UUID) -> list[Relation]:
        result = await self._session.execute(select(Relation).where(Relation.document_id == document_id))
        return list(result.scalars().all())
