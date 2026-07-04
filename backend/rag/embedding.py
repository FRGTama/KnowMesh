from backend.app.core.llm_manager import LLMManager


class Embedder:
    def __init__(self, manager: LLMManager):
        self._manager = manager

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._manager.embed(texts)
