from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    postgres_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/knowmesh",
        alias="DATABASE_URL",
    )
    postgres_pool_size: int = 10
    postgres_max_overflow: int = 20

    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    redis_queue_name: str = "ingestion"

    s3_endpoint: str = Field("", alias="S3_ENDPOINT")
    s3_bucket: str = Field("knowmesh", alias="S3_BUCKET")
    s3_access_key: str = Field("", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field("", alias="S3_SECRET_KEY")
    s3_region: str = Field("", alias="S3_REGION")

    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    deepseek_api_key: str = Field("", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field("https://api.deepseek.com/v1", alias="DEEPSEEK_BASE_URL")
    voyage_api_key: str = Field("", alias="VOYAGE_API_KEY")
    voyage_embed_model: str = "voyage-4-lite"
    voyage_rerank_model: str = "rerank-2.5-lite"

    retrieval_top_k: int = 20
    final_top_k: int = 5
    vector_search_weight: float = 0.6
    fts_search_weight: float = 0.25
    graph_search_weight: float = 0.15

    max_upload_size_mb: int = 50

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]