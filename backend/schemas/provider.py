from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    model_config = {"extra": "forbid"}

    provider: str = Field(pattern=r"^(openai|deepseek)$")
    model: str = Field(min_length=1)
    api_key: str = Field(min_length=1)


class ProviderStatus(BaseModel):
    model_config = {"from_attributes": True}

    configured: bool
    provider: str | None = None
    model: str | None = None
