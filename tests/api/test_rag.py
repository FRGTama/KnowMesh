from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.dependencies import (
    get_document_repo,
    get_retrieval_service,
    get_session,
)
from backend.app.main import create_app
from backend.schemas.query import Citation, QueryResponse
from tests.utils import make_test_settings


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr("backend.app.main.get_settings", make_test_settings)
    monkeypatch.setattr("backend.app.config.get_settings", make_test_settings)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: MagicMock()
    return TestClient(app)


def test_query_endpoint(client: TestClient, monkeypatch):
    chunk_id = uuid4()

    async def mock_query(query, document_ids=None, top_k=5):
        return QueryResponse(
            answer="Test answer",
            citations=[Citation(chunk_id=chunk_id, text="snippet")],
        )

    mock_service = MagicMock()
    mock_service.query = mock_query
    client.app.dependency_overrides[get_retrieval_service] = lambda: mock_service

    response = client.post(
        "/api/v1/query",
        json={"query": "what is mitochondria?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Test answer"
    assert len(data["citations"]) == 1
    assert data["citations"][0]["chunk_id"] == str(chunk_id)


def test_query_validation_empty_query(client: TestClient):
    response = client.post(
        "/api/v1/query",
        json={"query": ""},
    )
    assert response.status_code == 422


def test_list_documents_empty(client: TestClient):
    mock_repo = MagicMock()
    mock_repo.list = AsyncMock(return_value=[])
    client.app.dependency_overrides[get_document_repo] = lambda: mock_repo

    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    assert response.json() == []


def test_get_document_not_found(client: TestClient):
    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)
    client.app.dependency_overrides[get_document_repo] = lambda: mock_repo

    response = client.get(f"/api/v1/documents/{uuid4()}")
    assert response.status_code == 404


def test_delete_document_not_found(client: TestClient):
    mock_repo = MagicMock()
    mock_repo.delete = AsyncMock(return_value=False)
    client.app.dependency_overrides[get_document_repo] = lambda: mock_repo

    response = client.delete(f"/api/v1/documents/{uuid4()}")
    assert response.status_code == 404
