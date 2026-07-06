from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.relation import Entity


class EntityRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def insert_many(self, entities: list[Entity]) -> None:
        if not entities:
            return
        self._session.add_all(entities)
        await self._session.commit()

    async def get_by_document(self, document_id: UUID) -> list[Entity]:
        result = await self._session.execute(select(Entity).where(Entity.document_id == document_id))
        return list(result.scalars().all())

    async def find_by_names(self, names: list[str]) -> list[Entity]:
        if not names:
            return []
        result = await self._session.execute(select(Entity).where(Entity.name.in_(names)))
        return list(result.scalars().all())

    async def search_by_text(self, query_text: str) -> list[Entity]:
        """Find entities whose name appears as a substring in the query text."""
        tokens = [t.strip() for t in query_text.lower().split() if len(t.strip()) > 2]
        if not tokens:
            return []
        conditions = [Entity.name.ilike(f"%{token}%") for token in tokens]
        result = await self._session.execute(select(Entity).where(or_(*conditions)))
        return list(result.scalars().all())
