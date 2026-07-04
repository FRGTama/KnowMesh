from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings, get_settings
from backend.app.core.database import get_db_session
from backend.app.core.llm_manager import LLMManager, get_llm_manager
from backend.app.core.redis import get_redis
from backend.app.core.s3 import get_s3_client
from backend.rag.embedding import Embedder
from backend.rag.generator import Generator
from backend.rag.graph import GraphService
from backend.rag.reranker import Reranker
from backend.rag.retrieval import RetrievalService
from backend.repositories.chunk import ChunkRepository
from backend.repositories.document import DocumentRepository


async def get_session() -> AsyncGenerator[AsyncSession]:
    async for session in get_db_session():
        yield session


async def get_document_repo(session: AsyncSession = Depends(get_session)) -> DocumentRepository:
    return DocumentRepository(session)


async def get_chunk_repo(session: AsyncSession = Depends(get_session)) -> ChunkRepository:
    return ChunkRepository(session)


async def get_graph_service(session: AsyncSession = Depends(get_session)) -> GraphService:
    return GraphService(session)


async def get_retrieval_service(
    chunk_repo: ChunkRepository = Depends(get_chunk_repo),
    graph_service: GraphService = Depends(get_graph_service),
    manager: LLMManager = Depends(get_llm_manager),
    settings: Settings = Depends(get_settings),
) -> RetrievalService:
    return RetrievalService(
        chunk_repo=chunk_repo,
        graph_service=graph_service,
        embedder=Embedder(manager),
        reranker=Reranker(manager),
        generator=Generator(manager),
        settings=settings,
    )


__all__ = [
    "get_chunk_repo",
    "get_document_repo",
    "get_graph_service",
    "get_llm_manager",
    "get_redis",
    "get_retrieval_service",
    "get_session",
    "get_s3_client",
]
