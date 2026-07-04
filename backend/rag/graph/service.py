from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.chunk_entity import ChunkEntity
from backend.app.models.relation import Entity, Relation
from backend.repositories.chunk_entity import ChunkEntityRepository
from backend.repositories.entity import EntityRepository
from backend.repositories.relation import RelationRepository
from backend.schemas.entity import DocumentGraphResponse, EntityResponse
from backend.schemas.relation import RelationResponse


class GraphService:
    """Coordinates entity, relation, and chunk-entity link storage and retrieval."""

    def __init__(self, session: AsyncSession):
        self._entities = EntityRepository(session)
        self._relations = RelationRepository(session)
        self._chunk_entities = ChunkEntityRepository(session)
        self._session = session

    async def store(
        self,
        entities: list[Entity],
        relations: list[Relation],
        chunk_entity_links: list[ChunkEntity],
    ) -> None:
        """Persist entities, relations, and chunk-entity links in a single transaction."""
        if entities:
            self._session.add_all(entities)
        if relations:
            self._session.add_all(relations)
        if chunk_entity_links:
            self._session.add_all(chunk_entity_links)
        await self._session.commit()

    async def search(self, query_text: str, top_k: int = 20) -> list[tuple[UUID, float]]:
        """
        Graph-based chunk retrieval:
        1. Match entity names from query via ILIKE
        2. Find chunks linked to matched entities
        3. Score = match_count / total_matched_entities (Jaccard overlap)
        4. Return [(chunk_id, score)] sorted desc, capped at top_k
        """
        matched_entities = await self._entities.search_by_text(query_text)
        if not matched_entities:
            return []

        entity_ids = [e.id for e in matched_entities]
        total = len(matched_entities)

        chunk_matches = await self._chunk_entities.get_chunks_for_entities(entity_ids)
        scored = [(chunk_id, count / total) for chunk_id, count in chunk_matches]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    async def get_document_entities(self, document_id: UUID) -> list[EntityResponse]:
        entities = await self._entities.get_by_document(document_id)
        return [EntityResponse.model_validate(e) for e in entities]

    async def get_document_graph(self, document_id: UUID) -> DocumentGraphResponse:
        entities = await self._entities.get_by_document(document_id)
        relations = await self._relations.get_by_document(document_id)
        return DocumentGraphResponse(
            entities=[EntityResponse.model_validate(e) for e in entities],
            relations=[RelationResponse.model_validate(r) for r in relations],
        )
