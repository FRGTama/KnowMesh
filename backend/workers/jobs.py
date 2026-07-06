import asyncio
import uuid

from backend.app.config import get_settings
from backend.app.core.database import get_db_session
from backend.app.core.llm_manager import get_llm_manager
from backend.app.core.s3 import S3Client
from backend.rag.embedding import Embedder
from backend.rag.ingestion.chunking import RecursiveChunker
from backend.rag.ingestion.document_loader import _default_registry
from backend.rag.ingestion.pipeline import IngestionPipeline
from backend.repositories.chunk import ChunkRepository
from backend.repositories.document import DocumentRepository


def process_document(document_id: str) -> None:
    async def _run() -> None:
        settings = get_settings()
        s3 = S3Client(settings)
        manager = get_llm_manager()
        embedder = Embedder(manager)

        async for session in get_db_session():
            doc_repo = DocumentRepository(session)
            chunk_repo = ChunkRepository(session)
            pipeline = IngestionPipeline(
                s3=s3,
                chunk_repo=chunk_repo,
                document_repo=doc_repo,
                embedder=embedder,
                loader_registry=_default_registry,
                chunker=RecursiveChunker(),
            )
            await pipeline.process(uuid.UUID(document_id))
            break

    asyncio.run(_run())
