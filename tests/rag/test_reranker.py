from unittest.mock import AsyncMock

import pytest

from backend.app.core.llm_manager import LLMManager
from backend.rag.reranker import Reranker
from tests.utils import make_test_settings


@pytest.mark.asyncio
async def test_reranker_sorts_results_descending():
    manager = LLMManager(settings=make_test_settings())
    manager.rerank = AsyncMock(return_value=[(2, 0.5), (0, 0.9), (1, 0.7)])

    reranker = Reranker(manager)
    result = await reranker.rerank("query", ["a", "b", "c"])

    assert result == [(0, 0.9), (1, 0.7), (2, 0.5)]
    manager.rerank.assert_awaited_once_with("query", ["a", "b", "c"], top_k=None)


@pytest.mark.asyncio
async def test_reranker_passes_top_k():
    manager = LLMManager(settings=make_test_settings())
    manager.rerank = AsyncMock(return_value=[])

    reranker = Reranker(manager)
    await reranker.rerank("query", ["a"], top_k=5)
    manager.rerank.assert_awaited_once_with("query", ["a"], top_k=5)
