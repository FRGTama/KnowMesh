from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.models import Base
from backend.app.models.chunk import Chunk
from backend.app.models.document import Document
from backend.schemas.document import DocumentCreate
from tests.conftest import DB_AVAILABLE, TEST_DATABASE_URL


@pytest.fixture(autouse=True)
def _skip_if_no_db():
    if not DB_AVAILABLE:
        pytest.skip("test database not available")

_test_engine = create_async_engine(TEST_DATABASE_URL)
_TestSessionLocal = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with _TestSessionLocal() as session:
        yield session
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def sample_document(db_session: AsyncSession) -> Document:
    from backend.repositories.document import DocumentRepository

    repo = DocumentRepository(db_session)
    return await repo.create(
        DocumentCreate(
            filename="test.pdf",
            file_type=".pdf",
            file_size=1024,
            file_hash="abc123hash",
            strategy="recursive",
        )
    )


@pytest_asyncio.fixture
async def sample_chunks(db_session: AsyncSession, sample_document: Document) -> list[Chunk]:
    chunks = [
        Chunk(
            document_id=sample_document.id,
            index=i,
            text=f"chunk text {i}",
            embedding=[0.1] * 768,
            page=0,
            total_pages=1,
            strategy="recursive",
            tokens=100,
        )
        for i in range(3)
    ]
    db_session.add_all(chunks)
    await db_session.commit()
    return chunks
