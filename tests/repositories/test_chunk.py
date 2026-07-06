import pytest

from backend.repositories.chunk import ChunkRepository
from tests.repositories.conftest import db_session, sample_chunks, sample_document  # noqa: F401


@pytest.mark.asyncio
async def test_insert_and_get_by_document(db_session, sample_document):  # noqa: F811
    from backend.app.models.chunk import Chunk

    repo = ChunkRepository(db_session)
    chunks = [Chunk(document_id=sample_document.id, index=i, text=f"t{i}", tokens=10) for i in range(3)]
    await repo.insert_many(chunks)

    result = await repo.get_by_document(sample_document.id)
    assert len(result) == 3
    assert result[0].index == 0
    assert result[2].index == 2


@pytest.mark.asyncio
async def test_delete_by_document(db_session, sample_chunks):  # noqa: F811
    repo = ChunkRepository(db_session)
    doc_id = sample_chunks[0].document_id
    count = await repo.delete_by_document(doc_id)
    assert count == 3
    remaining = await repo.get_by_document(doc_id)
    assert remaining == []


@pytest.mark.asyncio
async def test_get_by_ids(db_session, sample_chunks):  # noqa: F811
    repo = ChunkRepository(db_session)
    ids = [c.id for c in sample_chunks[:2]]
    result = await repo.get_by_ids(ids)
    assert len(result) == 2
