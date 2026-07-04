from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.config import Settings
from backend.app.core.exceptions import LLMError
from backend.app.core.llm_manager import LLMManager, get_llm_manager


class FakeVoyageClient:
    def __init__(self):
        self.embed = AsyncMock()
        self.rerank = AsyncMock()


def _fake_embeddings(texts: list[str]) -> MagicMock:
    response = MagicMock()
    response.embeddings = [[0.1] * 768 for _ in range(len(texts))]
    return response


def _fake_reranking() -> MagicMock:
    response = MagicMock()
    result0 = MagicMock(index=1, relevance_score=0.9)
    result1 = MagicMock(index=0, relevance_score=0.5)
    response.results = [result0, result1]
    return response


def _fake_chat_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


def _make_settings(**overrides) -> Settings:
    defaults = {
        "postgres_url": "postgresql+asyncpg://x:x@localhost/x",
        "redis_url": "redis://localhost:6379/0",
        "s3_bucket": "test",
        "openai_api_key": "openai-key",
        "deepseek_api_key": "deepseek-key",
        "deepseek_base_url": "https://api.deepseek.com/v1",
        "voyage_api_key": "voyage-key",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
def settings() -> Settings:
    return _make_settings()


@pytest.fixture
def manager(settings: Settings) -> LLMManager:
    return LLMManager(settings=settings)


@pytest.fixture
def configured_manager(manager: LLMManager) -> LLMManager:
    fake_voyage = FakeVoyageClient()
    fake_voyage.embed.side_effect = lambda texts, model=None: _fake_embeddings(texts)
    fake_voyage.rerank.return_value = _fake_reranking()

    fake_openai_client = MagicMock()
    fake_openai_client.chat.completions.create.return_value = _fake_chat_response("answer")
    fake_generate_client = MagicMock()
    fake_generate_client.generate = AsyncMock(return_value="answer")

    manager._voyage_client = fake_voyage
    manager._generate_client = fake_generate_client
    manager.provider = "openai"
    manager.model = "gpt-4o"
    return manager


@pytest.mark.asyncio
async def test_configure_openai(manager: LLMManager):
    await manager.configure(provider="openai", model="gpt-4o", api_key="test-key")
    assert manager.provider == "openai"
    assert manager.model == "gpt-4o"
    assert manager.is_configured()


@pytest.mark.asyncio
async def test_configure_deepseek(manager: LLMManager):
    await manager.configure(provider="deepseek", model="deepseek-v4-flash", api_key="test-key")
    assert manager.provider == "deepseek"
    assert manager.model == "deepseek-v4-flash"


@pytest.mark.asyncio
async def test_configure_unsupported_provider(manager: LLMManager):
    with pytest.raises(LLMError, match="Unsupported provider"):
        await manager.configure(provider="anthropic", model="claude", api_key="test-key")


@pytest.mark.asyncio
async def test_configure_empty_key(manager: LLMManager):
    with pytest.raises(LLMError, match="API key must not be empty"):
        await manager.configure(provider="openai", model="gpt-4o", api_key="")


@pytest.mark.asyncio
async def test_configure_uses_provided_key_over_env(manager: LLMManager):
    await manager.configure(provider="openai", model="gpt-4o", api_key="explicit-key")
    assert manager._api_key == "explicit-key"


@pytest.mark.asyncio
async def test_embed_when_not_configured(manager: LLMManager):
    with pytest.raises(LLMError, match="not configured"):
        await manager.embed(["hello"])


@pytest.mark.asyncio
async def test_embed_delegates_to_voyage(configured_manager: LLMManager):
    embeddings = await configured_manager.embed(["hello", "world"])
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 768
    configured_manager._voyage_client.embed.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_empty_list(configured_manager: LLMManager):
    assert await configured_manager.embed([]) == []
    configured_manager._voyage_client.embed.assert_not_called()


@pytest.mark.asyncio
async def test_rerank_delegates_to_voyage(configured_manager: LLMManager):
    results = await configured_manager.rerank("query", ["a", "b"])
    assert results == [(1, 0.9), (0, 0.5)]


@pytest.mark.asyncio
async def test_rerank_empty_documents(configured_manager: LLMManager):
    assert await configured_manager.rerank("query", []) == []
    configured_manager._voyage_client.rerank.assert_not_called()


@pytest.mark.asyncio
async def test_generate_delegates_to_client(configured_manager: LLMManager):
    answer = await configured_manager.generate("sys", "user")
    assert answer == "answer"
    configured_manager._generate_client.generate.assert_awaited_once()


def test_get_llm_manager_singleton():
    m1 = get_llm_manager()
    m2 = get_llm_manager()
    assert m1 is m2
