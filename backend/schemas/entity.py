from typing import Any
from uuid import UUID

from pydantic import BaseModel

from backend.schemas.relation import RelationResponse


class EntityResponse(BaseModel):
    model_config = {"from_attributes": True, "extra": "forbid"}

    id: UUID
    document_id: UUID
    name: str
    type: str
    meta: dict[str, Any]


class DocumentGraphResponse(BaseModel):
    model_config = {"extra": "forbid"}

    entities: list[EntityResponse]
    relations: list[RelationResponse]
