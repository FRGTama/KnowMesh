from backend.app.config import Settings


def make_test_settings(**overrides) -> Settings:
    defaults = {
        "postgres_url": "postgresql+asyncpg://postgres:postgres@localhost:5432/knowmesh_test",
        "redis_url": "redis://localhost:6379/0",
        "s3_bucket": "test-bucket",
        "s3_access_key": "test-key",
        "s3_secret_key": "test-secret",
        "s3_endpoint": "http://localhost:9000",
        "s3_region": "us-east-1",
        "openai_api_key": "openai-test-key",
        "deepseek_api_key": "deepseek-test-key",
        "deepseek_base_url": "https://api.deepseek.com/v1",
        "voyage_api_key": "voyage-test-key",
    }
    defaults.update(overrides)
    return Settings(**defaults)
