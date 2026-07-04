from typing import Any
from uuid import UUID

from pydantic import BaseModel


class RelationResponse(BaseModel):
    model_config = {"from_attributes": True, "extra": "forbid"}

    id: UUID
    document_id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str
    weight: float
    meta: dict[str, Any]
