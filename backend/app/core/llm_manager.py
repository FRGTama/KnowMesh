import asyncio
from typing import Any, Protocol

from openai import AsyncOpenAI
from voyageai import AsyncClient as VoyageAsyncClient  # type: ignore[attr-defined]

from backend.app.config import Settings, get_settings
from backend.app.core.exceptions import LLMError

SUPPORTED_GENERATION_PROVIDERS = frozenset({"openai", "deepseek"})


class GenerateClient(Protocol):
    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str: ...


class OpenAICompatibleClient:
    def __init__(self, client: AsyncOpenAI):
        self._client = client

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if content is None:
            return ""
        return content


class LLMManager:
    # TODO: add EmbedClient and RerankClient protocols if supporting more
    # embedding/reranking providers beyond Voyage in the future.
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self.provider: str | None = None
        self.model: str | None = None
        self._api_key: str | None = None
        self._generate_client: GenerateClient | None = None
        self._voyage_client: Any | None = None
        self._configure_lock = asyncio.Lock()

    async def configure(
        self,
        provider: str,
        model: str,
        api_key: str,
    ) -> None:
        provider = provider.lower().strip()
        if provider not in SUPPORTED_GENERATION_PROVIDERS:
            raise LLMError(f"Unsupported provider: {provider}")

        key = self._resolve_api_key(api_key)
        if not key:
            raise LLMError("API key must not be empty")

        async with self._configure_lock:
            self.provider = provider
            self.model = model
            self._api_key = key
            self._generate_client = self._create_generate_client(provider, key)
            self._voyage_client = self._create_voyage_client()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._voyage_client:
            raise LLMError("LLMManager not configured. Call configure() first.")
        if not texts:
            return []
        response = await self._voyage_client.embed(
            texts,
            model=self._settings.voyage_embed_model,
        )
        return response.embeddings  # type: ignore[no-any-return]

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        if not self._voyage_client:
            raise LLMError("LLMManager not configured. Call configure() first.")
        if not documents:
            return []
        response = await self._voyage_client.rerank(
            query,
            documents,
            model=self._settings.voyage_rerank_model,
            top_k=top_k,
        )
        return [(result.index, result.relevance_score) for result in response.results]

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        if not self._generate_client or not self.model:
            raise LLMError("LLMManager not configured. Call configure() first.")
        return await self._generate_client.generate(
            model=self.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def is_configured(self) -> bool:
        return self._generate_client is not None and self._voyage_client is not None

    def _resolve_api_key(self, api_key: str) -> str:
        return api_key.strip()

    def _create_generate_client(self, provider: str, api_key: str) -> GenerateClient:
        base_url: str | None = None
        if provider == "deepseek":
            base_url = self._settings.deepseek_base_url
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        return OpenAICompatibleClient(client)

    def _create_voyage_client(self) -> Any:
        key = self._settings.voyage_api_key
        if not key:
            raise LLMError("Voyage API key not configured. Set VOYAGE_API_KEY.")
        return VoyageAsyncClient(api_key=key)


_llm_manager: LLMManager | None = None


def get_llm_manager() -> LLMManager:
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager
