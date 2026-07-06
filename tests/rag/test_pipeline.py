from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from backend.rag.ingestion.chunking import Chunk
from backend.rag.ingestion.document_loader import Document
from backend.rag.ingestion.pipeline import IngestionPipeline


@pytest.fixture
def doc_id() -> UUID:
    return uuid4()


@pytest.fixture
def mock_document(doc_id: UUID) -> MagicMock:
    doc = MagicMock()
    doc.id = doc_id
    doc.filename = "test.pdf"
    doc.s3_key = f"documents/{doc_id}/test.pdf"
    return doc


@pytest.fixture
def mock_s3() -> MagicMock:
    s3 = MagicMock()
    s3.download = AsyncMock()
    return s3


@pytest.fixture
def mock_doc_repo(mock_document: MagicMock) -> MagicMock:
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=mock_document)
    repo.update = AsyncMock(return_value=mock_document)
    return repo


@pytest.fixture
def mock_chunk_repo() -> MagicMock:
    repo = MagicMock()
    repo.insert_many = AsyncMock()
    return repo


@pytest.fixture
def mock_embedder() -> MagicMock:
    embedder = MagicMock()
    embedder.embed = AsyncMock()
    return embedder


class TestIngestionPipeline:
    @pytest.mark.asyncio
    async def test_process_happy_path(
        self,
        doc_id: UUID,
        mock_s3: MagicMock,
        mock_doc_repo: MagicMock,
        mock_chunk_repo: MagicMock,
        mock_embedder: MagicMock,
        monkeypatch,
    ):
        from backend.rag.ingestion import pipeline as pipeline_mod

        embedding = [0.1] * 768
        mock_embedder.embed = AsyncMock(return_value=[embedding, embedding])

        test_docs = [Document(text="Hello world", metadata={"document_id": str(doc_id), "page": 1, "total_pages": 3})]
        monkeypatch.setattr(pipeline_mod, "load", MagicMock(return_value=test_docs))

        chunk_0 = Chunk(
            text="Hello", document_id=doc_id, index=0, strategy="recursive", metadata={"page": 1, "total_pages": 3}
        )
        chunk_1 = Chunk(
            text="world", document_id=doc_id, index=1, strategy="recursive", metadata={"page": 1, "total_pages": 3}
        )
        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = [chunk_0, chunk_1]

        pipeline = IngestionPipeline(
            s3=mock_s3,
            chunk_repo=mock_chunk_repo,
            document_repo=mock_doc_repo,
            embedder=mock_embedder,
            loader_registry=MagicMock(),
            chunker=mock_chunker,
        )

        await pipeline.process(doc_id)

        assert mock_doc_repo.update.call_count >= 2

        mock_doc_repo.get_by_id.assert_awaited_once_with(doc_id)
        mock_s3.download.assert_awaited_once_with(mock_s3.download.call_args[0][0], mock_s3.download.call_args[0][1])
        mock_embedder.embed.assert_awaited_once_with(["Hello", "world"])
        mock_chunk_repo.insert_many.assert_awaited_once()
        inserted_chunks = mock_chunk_repo.insert_many.call_args[0][0]
        assert len(inserted_chunks) == 2
        assert all(c.document_id == doc_id for c in inserted_chunks)
        assert all(c.embedding == embedding for c in inserted_chunks)

    @pytest.mark.asyncio
    async def test_process_sets_failed_on_error(
        self,
        doc_id: UUID,
        mock_s3: MagicMock,
        mock_doc_repo: MagicMock,
        mock_chunk_repo: MagicMock,
        mock_embedder: MagicMock,
        monkeypatch,
    ):
        from backend.rag.ingestion import pipeline as pipeline_mod

        test_docs = [Document(text="Hello", metadata={"document_id": str(doc_id)})]
        monkeypatch.setattr(pipeline_mod, "load", MagicMock(return_value=test_docs))

        chunks = [Chunk(text="Hello", document_id=doc_id, index=0, strategy="recursive", metadata={})]
        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = chunks

        mock_embedder.embed = AsyncMock(side_effect=RuntimeError("embed failed"))

        pipeline = IngestionPipeline(
            s3=mock_s3,
            chunk_repo=mock_chunk_repo,
            document_repo=mock_doc_repo,
            embedder=mock_embedder,
            loader_registry=MagicMock(),
            chunker=mock_chunker,
        )

        with pytest.raises(RuntimeError, match="embed failed"):
            await pipeline.process(doc_id)

        failed_call = mock_doc_repo.update.call_args_list[-1]
        assert failed_call[0][0] == doc_id
        assert failed_call[0][1].status == "failed"
        assert "embed failed" in failed_call[0][1].error

        mock_chunk_repo.insert_many.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_process_embed_batching(
        self,
        doc_id: UUID,
        mock_s3: MagicMock,
        mock_doc_repo: MagicMock,
        mock_chunk_repo: MagicMock,
        mock_embedder: MagicMock,
        monkeypatch,
    ):
        from backend.rag.ingestion import pipeline as pipeline_mod

        async def embed_batch(texts: list[str]) -> list[list[float]]:
            return [[0.1] * 768 for _ in texts]

        mock_embedder.embed = AsyncMock(side_effect=embed_batch)

        test_docs = [Document(text="Hello world", metadata={"document_id": str(doc_id)})]
        monkeypatch.setattr(pipeline_mod, "load", MagicMock(return_value=test_docs))

        chunks = [
            Chunk(text=f"chunk_{i}", document_id=doc_id, index=i, strategy="recursive", metadata={}) for i in range(200)
        ]
        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = chunks

        pipeline = IngestionPipeline(
            s3=mock_s3,
            chunk_repo=mock_chunk_repo,
            document_repo=mock_doc_repo,
            embedder=mock_embedder,
            loader_registry=MagicMock(),
            chunker=mock_chunker,
            embed_batch_size=96,
        )

        await pipeline.process(doc_id)

        assert mock_embedder.embed.call_count == 3
        assert len(mock_embedder.embed.call_args_list[0][0][0]) == 96
        assert len(mock_embedder.embed.call_args_list[1][0][0]) == 96
        assert len(mock_embedder.embed.call_args_list[2][0][0]) == 8

        inserted = mock_chunk_repo.insert_many.call_args[0][0]
        assert len(inserted) == 200

    @pytest.mark.asyncio
    async def test_process_empty_document(
        self,
        doc_id: UUID,
        mock_s3: MagicMock,
        mock_doc_repo: MagicMock,
        mock_chunk_repo: MagicMock,
        mock_embedder: MagicMock,
        monkeypatch,
    ):
        from backend.rag.ingestion import pipeline as pipeline_mod

        monkeypatch.setattr(pipeline_mod, "load", MagicMock(return_value=[]))

        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = []

        pipeline = IngestionPipeline(
            s3=mock_s3,
            chunk_repo=mock_chunk_repo,
            document_repo=mock_doc_repo,
            embedder=mock_embedder,
            loader_registry=MagicMock(),
            chunker=mock_chunker,
        )

        await pipeline.process(doc_id)

        mock_embedder.embed.assert_not_awaited()
        mock_chunk_repo.insert_many.assert_not_awaited()

        completed_call = mock_doc_repo.update.call_args_list[-1]
        assert completed_call[0][0] == doc_id
        assert completed_call[0][1].status == "completed"
        assert completed_call[0][1].chunk_count == 0
