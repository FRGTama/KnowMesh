from backend.app.core.llm_manager import LLMManager


class Reranker:
    def __init__(self, manager: LLMManager):
        self._manager = manager

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        scored = await self._manager.rerank(query, documents, top_k=top_k)
        return sorted(scored, key=lambda item: item[1], reverse=True)
