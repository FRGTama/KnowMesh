from pathlib import Path
from typing import Any

from aiobotocore.session import AioSession, get_session

from backend.app.config import Settings, get_settings


class S3Client:
    # TODO: evaluate reusing a single aiobotocore client per worker/process
    # to reduce connection setup overhead under high request volume.
    def __init__(self, settings: Settings):
        self._bucket = settings.s3_bucket
        self._session: AioSession = get_session()
        self._client_kwargs: dict[str, str | None] = {
            "endpoint_url": settings.s3_endpoint or None,
            "aws_access_key_id": settings.s3_access_key or None,
            "aws_secret_access_key": settings.s3_secret_key or None,
            "region_name": settings.s3_region or None,
        }

    def _create_client(self) -> Any:
        return self._session.create_client("s3", **self._client_kwargs)

    async def upload(self, data: bytes, key: str) -> str:
        async with self._create_client() as client:
            await client.put_object(Bucket=self._bucket, Key=key, Body=data)
        return key

    async def download(self, key: str, destination: Path) -> Path:
        async with self._create_client() as client:
            response = await client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            try:
                data = await body.read()
            finally:
                await body.close()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return destination

    async def delete(self, key: str) -> None:
        async with self._create_client() as client:
            await client.delete_object(Bucket=self._bucket, Key=key)


_s3_client: S3Client | None = None


def get_s3_client() -> S3Client:
    global _s3_client
    if _s3_client is None:
        _s3_client = S3Client(get_settings())
    return _s3_client
