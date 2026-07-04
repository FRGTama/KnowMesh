from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.rag.graph import GraphService


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def graph_service(mock_session: MagicMock) -> GraphService:
    service = GraphService(mock_session)
    service._entities = MagicMock()
    service._relations = MagicMock()
    service._chunk_entities = MagicMock()
    return service


@pytest.mark.asyncio
async def test_search_no_matching_entities(graph_service: GraphService):
    graph_service._entities.search_by_text = AsyncMock(return_value=[])
    result = await graph_service.search("nothing matches", top_k=10)
    assert result == []


@pytest.mark.asyncio
async def test_search_scores_by_jaccard_overlap(graph_service: GraphService):
    e1 = MagicMock(id=uuid4())
    e2 = MagicMock(id=uuid4())
    chunk_id = uuid4()

    graph_service._entities.search_by_text = AsyncMock(return_value=[e1, e2])
    graph_service._chunk_entities.get_chunks_for_entities = AsyncMock(
        return_value=[(chunk_id, 2)]
    )

    result = await graph_service.search("matching query", top_k=10)
    assert len(result) == 1
    assert result[0][0] == chunk_id
    assert result[0][1] == 1.0  # 2 matches / 2 total entities


@pytest.mark.asyncio
async def test_search_partial_overlap(graph_service: GraphService):
    e1 = MagicMock(id=uuid4())
    e2 = MagicMock(id=uuid4())
    e3 = MagicMock(id=uuid4())
    chunk_a = uuid4()
    chunk_b = uuid4()

    graph_service._entities.search_by_text = AsyncMock(return_value=[e1, e2, e3])
    graph_service._chunk_entities.get_chunks_for_entities = AsyncMock(
        return_value=[(chunk_a, 2), (chunk_b, 1)]
    )

    result = await graph_service.search("query", top_k=10)
    assert len(result) == 2
    assert result[0][0] == chunk_a  # higher score first
    assert result[0][1] == pytest.approx(2 / 3)
    assert result[1][0] == chunk_b
    assert result[1][1] == pytest.approx(1 / 3)


@pytest.mark.asyncio
async def test_search_respects_top_k(graph_service: GraphService):
    entities = [MagicMock(id=uuid4()) for _ in range(3)]
    chunk_ids = [uuid4() for _ in range(5)]

    graph_service._entities.search_by_text = AsyncMock(return_value=entities)
    graph_service._chunk_entities.get_chunks_for_entities = AsyncMock(
        return_value=[(cid, 1) for cid in chunk_ids]
    )

    result = await graph_service.search("query", top_k=3)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_get_document_graph_validates_response(graph_service: GraphService):
    doc_id = uuid4()
    entity = MagicMock()
    entity.id = uuid4()
    entity.document_id = doc_id
    entity.name = "test"
    entity.type = "concept"
    entity.meta = {}

    relation = MagicMock()
    relation.id = uuid4()
    relation.document_id = doc_id
    relation.source_entity_id = uuid4()
    relation.target_entity_id = uuid4()
    relation.relation_type = "relates_to"
    relation.weight = 1.0
    relation.meta = {}

    graph_service._entities.get_by_document = AsyncMock(return_value=[entity])
    graph_service._relations.get_by_document = AsyncMock(return_value=[relation])

    result = await graph_service.get_document_graph(doc_id)
    assert len(result.entities) == 1
    assert len(result.relations) == 1
    assert result.entities[0].name == "test"
