import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/knowmesh_test",
)


def _db_available() -> bool:
    try:
        import sqlalchemy as sa
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(TEST_DATABASE_URL)

        async def check():
            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))

        asyncio.run(check())
        asyncio.run(engine.dispose())
        return True
    except Exception:
        return False


DB_AVAILABLE = _db_available()
