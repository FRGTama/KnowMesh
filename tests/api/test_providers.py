from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.app.core.exceptions import LLMError
from backend.app.core.llm_manager import LLMManager, get_llm_manager
from backend.app.main import create_app
from tests.utils import make_test_settings


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr("backend.app.main.get_settings", make_test_settings)
    monkeypatch.setattr("backend.app.config.get_settings", make_test_settings)
    manager = LLMManager(settings=make_test_settings())
    manager.configure = AsyncMock()
    monkeypatch.setattr("backend.app.api.providers.get_llm_manager", lambda: manager)
    return TestClient(create_app())


def test_get_status_not_configured(client: TestClient):
    response = client.get("/api/v1/providers/status")
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is False
    assert data["provider"] is None


def test_configure_provider(client: TestClient):
    response = client.post(
        "/api/v1/providers/configure",
        json={"provider": "openai", "model": "gpt-4o", "api_key": "sk-test"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-4o"


def test_configure_invalid_provider(client: TestClient):
    response = client.post(
        "/api/v1/providers/configure",
        json={"provider": "anthropic", "model": "claude", "api_key": "sk-test"},
    )
    assert response.status_code == 422


def test_configure_bad_request(monkeypatch):
    monkeypatch.setattr("backend.app.main.get_settings", make_test_settings)
    monkeypatch.setattr("backend.app.config.get_settings", make_test_settings)
    manager = get_llm_manager()
    manager.configure = AsyncMock(side_effect=LLMError("missing key"))
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/providers/configure",
        json={"provider": "openai", "model": "gpt-4o", "api_key": "sk-test"},
    )
    assert response.status_code == 400
    assert "missing key" in response.json()["detail"]
