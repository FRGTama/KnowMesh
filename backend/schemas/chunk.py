from uuid import UUID

from pydantic import BaseModel


class ChunkResponse(BaseModel):
    model_config = {"from_attributes": True, "extra": "forbid"}

    id: UUID
    document_id: UUID
    index: int
    text: str
    page: int
    total_pages: int
    strategy: str
    tokens: int