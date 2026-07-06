from uuid import UUID

from backend.app.config import Settings
from backend.app.models.chunk import Chunk
from backend.rag.embedding import Embedder
from backend.rag.generator import Generator
from backend.rag.graph import GraphService
from backend.rag.reranker import Reranker
from backend.repositories.chunk import ChunkRepository
from backend.schemas.query import Citation, QueryResponse


class RetrievalService:
    """Orchestrates hybrid search (vector + FTS + graph) → rerank → generate."""

    def __init__(
        self,
        chunk_repo: ChunkRepository,
        graph_service: GraphService,
        embedder: Embedder,
        reranker: Reranker,
        generator: Generator,
        settings: Settings,
    ):
        self._chunk_repo = chunk_repo
        self._graph = graph_service
        self._embedder = embedder
        self._reranker = reranker
        self._generator = generator
        self._settings = settings

    async def query(
        self,
        query: str,
        document_ids: list[UUID] | None = None,
        top_k: int = 5,
    ) -> QueryResponse:
        chunks = await self._search(query, document_ids)
        if not chunks:
            return QueryResponse(answer="No relevant information found.", citations=[])

        chunk_texts = [c.text for c in chunks]
        reranked = await self._reranker.rerank(query, chunk_texts, top_k=top_k)
        top_chunks = [chunks[idx] for idx, _ in reranked]

        contexts = [c.text for c in top_chunks]
        answer = await self._generator.generate(query, contexts)
        citations = [Citation(chunk_id=c.id, text=c.text[:200]) for c in top_chunks]
        return QueryResponse(answer=answer, citations=citations)

    async def _search(
        self,
        query: str,
        document_ids: list[UUID] | None = None,
    ) -> list[Chunk]:
        top_k = self._settings.retrieval_top_k

        query_embedding = (await self._embedder.embed([query]))[0]

        vector_results = await self._chunk_repo.search_vector(query_embedding, top_k=top_k, document_ids=document_ids)
        fts_results = await self._chunk_repo.search_fts(query, top_k=top_k, document_ids=document_ids)
        graph_results = await self._graph.search(query, top_k=top_k)

        return self._merge_scores(vector_results, fts_results, graph_results)

    def _merge_scores(
        self,
        vector_results: list[tuple[Chunk, float]],
        fts_results: list[tuple[Chunk, float]],
        graph_results: list[tuple[UUID, float]],
    ) -> list[Chunk]:
        w_vec = self._settings.vector_search_weight
        w_fts = self._settings.fts_search_weight
        w_graph = self._settings.graph_search_weight

        max_fts = max((s for _, s in fts_results), default=1.0) or 1.0

        scores: dict[UUID, float] = {}
        chunk_map: dict[UUID, Chunk] = {}

        for chunk, score in vector_results:
            scores[chunk.id] = scores.get(chunk.id, 0.0) + w_vec * score
            chunk_map[chunk.id] = chunk

        for chunk, raw_rank in fts_results:
            normalized = raw_rank / max_fts
            scores[chunk.id] = scores.get(chunk.id, 0.0) + w_fts * normalized
            chunk_map[chunk.id] = chunk

        for chunk_id, score in graph_results:
            if chunk_id in chunk_map:
                scores[chunk_id] = scores.get(chunk_id, 0.0) + w_graph * score

        ranked_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
        top_k = self._settings.retrieval_top_k
        return [chunk_map[cid] for cid in ranked_ids[:top_k] if cid in chunk_map]
