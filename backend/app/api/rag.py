from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.dependencies import (
    get_chunk_repo,
    get_document_repo,
    get_graph_service,
    get_retrieval_service,
)
from backend.rag.graph import GraphService
from backend.rag.retrieval import RetrievalService
from backend.repositories.chunk import ChunkRepository
from backend.repositories.document import DocumentRepository
from backend.schemas.chunk import ChunkResponse
from backend.schemas.document import DocumentResponse
from backend.schemas.entity import DocumentGraphResponse, EntityResponse
from backend.schemas.query import QueryRequest, QueryResponse

router = APIRouter(tags=["rag"])


@router.post("/query", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    service: RetrievalService = Depends(get_retrieval_service),
) -> QueryResponse:
    return await service.query(body.query, body.document_ids, body.top_k)


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    repo: DocumentRepository = Depends(get_document_repo),
    limit: int = 50,
    offset: int = 0,
) -> list[DocumentResponse]:
    docs = await repo.list(limit=limit, offset=offset)
    return [DocumentResponse.model_validate(d) for d in docs]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    repo: DocumentRepository = Depends(get_document_repo),
) -> DocumentResponse:
    doc = await repo.get_by_id(document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: UUID,
    repo: DocumentRepository = Depends(get_document_repo),
) -> dict[str, bool | str]:
    deleted = await repo.delete(document_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return {"deleted": True, "document_id": str(document_id)}


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkResponse])
async def get_document_chunks(
    document_id: UUID,
    repo: ChunkRepository = Depends(get_chunk_repo),
) -> list[ChunkResponse]:
    chunks = await repo.get_by_document(document_id)
    return [ChunkResponse.model_validate(c) for c in chunks]


@router.get("/documents/{document_id}/entities", response_model=list[EntityResponse])
async def get_document_entities(
    document_id: UUID,
    graph: GraphService = Depends(get_graph_service),
) -> list[EntityResponse]:
    return await graph.get_document_entities(document_id)


@router.get("/documents/{document_id}/graph", response_model=DocumentGraphResponse)
async def get_document_graph(
    document_id: UUID,
    graph: GraphService = Depends(get_graph_service),
) -> DocumentGraphResponse:
    return await graph.get_document_graph(document_id)
