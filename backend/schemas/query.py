from uuid import UUID

from pydantic import BaseModel, Field


class Citation(BaseModel):
    model_config = {"extra": "forbid"}

    chunk_id: UUID
    text: str


class QueryRequest(BaseModel):
    model_config = {"extra": "forbid"}

    query: str = Field(min_length=1)
    document_ids: list[UUID] | None = None
    top_k: int = Field(default=5, ge=1, le=50)


class QueryResponse(BaseModel):
    model_config = {"extra": "forbid"}

    answer: str
    citations: list[Citation]
