from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    model_config = {"extra": "forbid"}

    filename: str
    file_type: str = Field(max_length=20)
    file_size: int = Field(default=0, ge=0)
    file_hash: str | None = None
    strategy: str = "recursive"
    meta: dict[str, Any] = Field(default_factory=dict)


class DocumentUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    status: str | None = None
    strategy: str | None = None
    chunk_count: int | None = None
    error: str | None = None
    meta: dict[str, Any] | None = None


class DocumentResponse(BaseModel):
    model_config = {"from_attributes": True, "extra": "forbid"}

    id: UUID
    filename: str
    file_type: str
    file_size: int
    file_hash: str | None
    status: str
    strategy: str
    chunk_count: int
    error: str | None
    meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime
