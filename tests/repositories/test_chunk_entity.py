import pytest

from backend.app.models.chunk_entity import ChunkEntity
from backend.repositories.chunk_entity import ChunkEntityRepository
from tests.repositories.conftest import db_session, sample_chunks, sample_document  # noqa: F401


@pytest.mark.asyncio
async def test_insert_and_get_by_chunk(db_session, sample_chunks):  # noqa: F811
    from backend.app.models.relation import Entity

    entity = Entity(document_id=sample_chunks[0].document_id, name="test-entity", type="concept")
    db_session.add(entity)
    await db_session.commit()
    await db_session.refresh(entity)

    repo = ChunkEntityRepository(db_session)
    link = ChunkEntity(chunk_id=sample_chunks[0].id, entity_id=entity.id)
    await repo.insert_many([link])

    result = await repo.get_by_chunk(sample_chunks[0].id)
    assert len(result) == 1
    assert result[0].entity_id == entity.id


@pytest.mark.asyncio
async def test_get_by_entity(db_session, sample_chunks, sample_document):  # noqa: F811
    from backend.app.models.relation import Entity

    entity = Entity(document_id=sample_document.id, name="keyword", type="topic")
    db_session.add(entity)
    await db_session.commit()
    await db_session.refresh(entity)

    links = [ChunkEntity(chunk_id=c.id, entity_id=entity.id) for c in sample_chunks[:2]]
    repo = ChunkEntityRepository(db_session)
    await repo.insert_many(links)

    result = await repo.get_by_entity(entity.id)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_chunks_for_entities(db_session, sample_chunks, sample_document):  # noqa: F811
    from backend.app.models.relation import Entity

    e1 = Entity(document_id=sample_document.id, name="alpha", type="concept")
    e2 = Entity(document_id=sample_document.id, name="beta", type="concept")
    db_session.add_all([e1, e2])
    await db_session.commit()
    await db_session.refresh(e1)
    await db_session.refresh(e2)

    repo = ChunkEntityRepository(db_session)
    await repo.insert_many(
        [
            ChunkEntity(chunk_id=sample_chunks[0].id, entity_id=e1.id),
            ChunkEntity(chunk_id=sample_chunks[0].id, entity_id=e2.id),
            ChunkEntity(chunk_id=sample_chunks[1].id, entity_id=e1.id),
        ]
    )

    result = await repo.get_chunks_for_entities([e1.id, e2.id])
    assert len(result) == 2
    chunk0_entry = next(r for r in result if r[0] == sample_chunks[0].id)
    assert chunk0_entry[1] == 2
    chunk1_entry = next(r for r in result if r[0] == sample_chunks[1].id)
    assert chunk1_entry[1] == 1


@pytest.mark.asyncio
async def test_empty_entity_ids(db_session):  # noqa: F811
    repo = ChunkEntityRepository(db_session)
    assert await repo.get_chunks_for_entities([]) == []
