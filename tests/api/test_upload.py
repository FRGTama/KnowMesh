from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings, get_settings
from tests.utils import make_test_settings


def _make_mock_document(**kwargs):
    doc_id = kwargs.get("id", uuid4())
    doc = MagicMock()
    doc.id = doc_id
    doc.filename = kwargs.get("filename", "test.pdf")
    doc.file_size = kwargs.get("file_size", 1024)
    doc.file_hash = kwargs.get("file_hash", "feedface")
    doc.s3_key = kwargs.get("s3_key", "documents/x/test.pdf")
    doc.status = kwargs.get("status", "queued")
    doc.created_at = kwargs.get("created_at", datetime.now())
    return doc


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr("backend.app.main.get_settings", make_test_settings)

    from backend.app.dependencies import get_document_repo, get_redis, get_s3_client, get_session
    from backend.app.main import create_app

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: make_test_settings()
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[get_redis] = lambda: MagicMock()
    app.dependency_overrides[get_s3_client] = lambda: MagicMock()
    app.dependency_overrides[get_document_repo] = lambda: MagicMock()

    return TestClient(app)


class TestUpload:
    def test_upload_success(self, client: TestClient, monkeypatch):
        from backend.app.dependencies import get_document_repo, get_s3_client

        doc_id = uuid4()
        mock_doc = _make_mock_document(id=doc_id, status="queued")

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_hash = AsyncMock(return_value=None)
        mock_doc_repo.create = AsyncMock(return_value=mock_doc)

        mock_s3 = MagicMock()
        mock_s3.upload = AsyncMock()

        mock_queue = MagicMock()
        mock_queue.enqueue = MagicMock()
        import rq

        monkeypatch.setattr(rq, "Queue", MagicMock(return_value=mock_queue))

        client.app.dependency_overrides[get_document_repo] = lambda: mock_doc_repo
        client.app.dependency_overrides[get_s3_client] = lambda: mock_s3

        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", b"pdf content goes here", "application/pdf")},
            data={"strategy": "recursive"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == str(doc_id)
        assert data["filename"] == "test.pdf"
        assert data["status"] == "queued"
        mock_s3.upload.assert_awaited_once()
        mock_doc_repo.create.assert_awaited_once()
        mock_queue.enqueue.assert_called_once_with("backend.workers.jobs.process_document", str(doc_id))

    def test_upload_unsupported_extension(self, client: TestClient):
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("data.xyz", b"stuff", "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "Unsupported" in response.json()["detail"]

    def test_upload_exceeds_size_limit(self, client: TestClient):
        from backend.app.dependencies import get_document_repo

        tiny = Settings(**make_test_settings().model_dump() | {"max_upload_size_mb": 0})
        client.app.dependency_overrides[get_settings] = lambda: tiny

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_hash = AsyncMock(return_value=None)
        client.app.dependency_overrides[get_document_repo] = lambda: mock_doc_repo

        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", b"x", "application/pdf")},
        )
        assert response.status_code == 413

    def test_upload_duplicate_returns_existing(self, client: TestClient, monkeypatch):
        from backend.app.dependencies import get_document_repo, get_s3_client

        doc_id = uuid4()
        existing_doc = _make_mock_document(id=doc_id, status="completed", file_hash="dup-hash")

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_hash = AsyncMock(return_value=existing_doc)

        mock_s3 = MagicMock()
        mock_s3.upload = AsyncMock()

        import rq

        monkeypatch.setattr(rq, "Queue", MagicMock())

        client.app.dependency_overrides[get_document_repo] = lambda: mock_doc_repo
        client.app.dependency_overrides[get_s3_client] = lambda: mock_s3

        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", b"same content", "application/pdf")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == str(doc_id)
        assert data["status"] == "completed"
        mock_s3.upload.assert_not_awaited()
        mock_doc_repo.create.assert_not_called()
