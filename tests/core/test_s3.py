from unittest.mock import AsyncMock, patch

import pytest

from backend.app.config import Settings
from backend.app.core.s3 import S3Client


class FakeS3Body:
    def __init__(self, data: bytes):
        self._data = data

    async def read(self) -> bytes:
        return self._data

    async def close(self) -> None:
        pass


class FakeS3Client:
    def __init__(self):
        self.put_object = AsyncMock()
        self.get_object = AsyncMock()
        self.delete_object = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def s3_client():
    settings = Settings(
        postgres_url="postgresql+asyncpg://x:x@localhost/x",
        s3_bucket="test-bucket",
        s3_access_key="key",
        s3_secret_key="secret",
        s3_endpoint="http://localhost:9000",
        s3_region="us-east-1",
    )
    return S3Client(settings)


@pytest.mark.asyncio
async def test_upload(s3_client, tmp_path):
    fake = FakeS3Client()
    with patch.object(s3_client, "_create_client", return_value=fake):
        key = await s3_client.upload(b"hello", "doc/file.txt")
    assert key == "doc/file.txt"
    fake.put_object.assert_called_once_with(Bucket="test-bucket", Key="doc/file.txt", Body=b"hello")


@pytest.mark.asyncio
async def test_download(s3_client, tmp_path):
    fake = FakeS3Client()
    fake.get_object.return_value = {"Body": FakeS3Body(b"file content")}
    dest = tmp_path / "output" / "file.txt"
    with patch.object(s3_client, "_create_client", return_value=fake):
        result = await s3_client.download("doc/file.txt", dest)
    assert result == dest
    assert dest.read_bytes() == b"file content"


@pytest.mark.asyncio
async def test_delete(s3_client):
    fake = FakeS3Client()
    with patch.object(s3_client, "_create_client", return_value=fake):
        await s3_client.delete("doc/file.txt")
    fake.delete_object.assert_called_once_with(Bucket="test-bucket", Key="doc/file.txt")
