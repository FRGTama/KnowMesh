import pytest

from backend.repositories.document import DocumentRepository
from backend.schemas.document import DocumentCreate, DocumentUpdate
from tests.repositories.conftest import db_session  # noqa: F401


@pytest.mark.asyncio
async def test_create_and_get_by_id(db_session):  # noqa: F811
    repo = DocumentRepository(db_session)
    doc = await repo.create(DocumentCreate(filename="doc.pdf", file_type=".pdf", file_size=500, file_hash="hash123"))
    assert doc.id is not None
    assert doc.status == "queued"

    fetched = await repo.get_by_id(doc.id)
    assert fetched is not None
    assert fetched.filename == "doc.pdf"


@pytest.mark.asyncio
async def test_get_by_hash(db_session):  # noqa: F811
    repo = DocumentRepository(db_session)
    await repo.create(DocumentCreate(filename="a.pdf", file_type=".pdf", file_size=100, file_hash="uniquehash"))
    found = await repo.get_by_hash("uniquehash")
    assert found is not None
    assert found.filename == "a.pdf"

    missing = await repo.get_by_hash("nonexistent")
    assert missing is None


@pytest.mark.asyncio
async def test_list_with_pagination(db_session):  # noqa: F811
    repo = DocumentRepository(db_session)
    for i in range(5):
        await repo.create(DocumentCreate(filename=f"file{i}.txt", file_type=".txt", file_size=10, file_hash=f"h{i}"))
    docs = await repo.list(limit=2, offset=0)
    assert len(docs) == 2
    all_docs = await repo.list(limit=50, offset=0)
    assert len(all_docs) == 5


@pytest.mark.asyncio
async def test_update(db_session):  # noqa: F811
    repo = DocumentRepository(db_session)
    doc = await repo.create(DocumentCreate(filename="u.txt", file_type=".txt", file_size=10))
    updated = await repo.update(doc.id, DocumentUpdate(status="completed", chunk_count=42))
    assert updated is not None
    assert updated.status == "completed"
    assert updated.chunk_count == 42


@pytest.mark.asyncio
async def test_delete(db_session):  # noqa: F811
    repo = DocumentRepository(db_session)
    doc = await repo.create(DocumentCreate(filename="d.txt", file_type=".txt", file_size=10))
    assert await repo.delete(doc.id) is True
    assert await repo.get_by_id(doc.id) is None
