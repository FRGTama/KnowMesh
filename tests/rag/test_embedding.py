from unittest.mock import AsyncMock

import pytest

from backend.app.core.llm_manager import LLMManager
from backend.rag.embedding import Embedder
from tests.utils import make_test_settings


@pytest.mark.asyncio
async def test_embedder_delegates_to_manager():
    manager = LLMManager(settings=make_test_settings())
    manager.embed = AsyncMock(return_value=[[0.0, 0.2, 0.3], [1.0, 0.2, 0.3]])  # type: ignore[method-assign]

    embedder = Embedder(manager)
    result = await embedder.embed(["a", "b"])
    assert result == [[0.0, 0.2, 0.3], [1.0, 0.2, 0.3]]
