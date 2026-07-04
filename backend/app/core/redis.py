import redis.asyncio as redis_lib

from backend.app.config import get_settings

_redis_client: redis_lib.Redis | None = None


def get_redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis_lib.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
