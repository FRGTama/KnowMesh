from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from backend.app.config import Settings
from backend.rag.retrieval import RetrievalService
from tests.utils import make_test_settings


def _make_chunk(cid: UUID, text: str) -> MagicMock:
    chunk = MagicMock()
    chunk.id = cid
    chunk.text = text
    return chunk


@pytest.fixture
def settings() -> Settings:
    return make_test_settings()


@pytest.fixture
def retrieval_service(settings: Settings) -> RetrievalService:
    service = RetrievalService(
        chunk_repo=MagicMock(),
        graph_service=MagicMock(),
        embedder=MagicMock(),
        reranker=MagicMock(),
        generator=MagicMock(),
        settings=settings,
    )
    service._embedder.embed = AsyncMock(return_value=[[0.1] * 768])
    service._reranker.rerank = AsyncMock(return_value=[(0, 0.9), (1, 0.8)])
    service._generator.generate = AsyncMock(return_value="generated answer")
    return service


@pytest.mark.asyncio
async def test_query_no_results(retrieval_service: RetrievalService):
    retrieval_service._chunk_repo.search_vector = AsyncMock(return_value=[])
    retrieval_service._chunk_repo.search_fts = AsyncMock(return_value=[])
    retrieval_service._graph.search = AsyncMock(return_value=[])

    result = await retrieval_service.query("test query")
    assert result.answer == "No relevant information found."
    assert result.citations == []


@pytest.mark.asyncio
async def test_query_returns_answer_and_citations(retrieval_service: RetrievalService):
    cid1 = uuid4()
    cid2 = uuid4()
    chunk1 = _make_chunk(cid1, "context one about mitochondria")
    chunk2 = _make_chunk(cid2, "context two about ATP synthesis")

    retrieval_service._chunk_repo.search_vector = AsyncMock(
        return_value=[(chunk1, 0.9), (chunk2, 0.7)]
    )
    retrieval_service._chunk_repo.search_fts = AsyncMock(return_value=[])
    retrieval_service._graph.search = AsyncMock(return_value=[])

    result = await retrieval_service.query("mitochondria ATP")
    assert result.answer == "generated answer"
    assert len(result.citations) == 2
    assert result.citations[0].chunk_id == cid1
    assert "context one" in result.citations[0].text


@pytest.mark.asyncio
async def test_merge_scores_weights_all_three(retrieval_service: RetrievalService):
    cid = uuid4()
    chunk = _make_chunk(cid, "shared chunk")

    vec_results = [(chunk, 0.8)]
    fts_results = [(chunk, 2.0)]
    graph_results = [(cid, 0.5)]

    merged = retrieval_service._merge_scores(vec_results, fts_results, graph_results)
    assert len(merged) == 1
    assert merged[0].id == cid


@pytest.mark.asyncio
async def test_merge_scores_handles_missing_graph(retrieval_service: RetrievalService):
    cid = uuid4()
    chunk = _make_chunk(cid, "vector-only chunk")

    merged = retrieval_service._merge_scores(
        vector_results=[(chunk, 0.9)],
        fts_results=[],
        graph_results=[],
    )
    assert len(merged) == 1
    assert merged[0].id == cid


@pytest.mark.asyncio
async def test_merge_scores_fts_normalization(retrieval_service: RetrievalService):
    cid_a = uuid4()
    cid_b = uuid4()
    chunk_a = _make_chunk(cid_a, "high rank")
    chunk_b = _make_chunk(cid_b, "low rank")

    merged = retrieval_service._merge_scores(
        vector_results=[],
        fts_results=[(chunk_a, 4.0), (chunk_b, 1.0)],
        graph_results=[],
    )
    assert merged[0].id == cid_a  # higher fts rank first
    assert merged[1].id == cid_b
