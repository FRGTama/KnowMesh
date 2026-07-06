import hashlib
from uuid import UUID, uuid4

import rq
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from redis import Redis

from backend.app.config import Settings, get_settings
from backend.app.core.redis import get_redis
from backend.app.core.s3 import S3Client, get_s3_client
from backend.app.dependencies import (
    get_chunk_repo,
    get_document_repo,
    get_graph_service,
    get_retrieval_service,
)
from backend.rag.graph import GraphService
from backend.rag.ingestion.document_loader import _default_registry
from backend.rag.retrieval import RetrievalService
from backend.repositories.chunk import ChunkRepository
from backend.repositories.document import DocumentRepository
from backend.schemas.chunk import ChunkResponse
from backend.schemas.document import DocumentCreate, DocumentResponse, UploadResponse
from backend.schemas.entity import DocumentGraphResponse, EntityResponse
from backend.schemas.query import QueryRequest, QueryResponse

router = APIRouter(tags=["rag"])


@router.post("/documents/upload", response_model=UploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    strategy: str = Form("recursive"),
    document_repo: DocumentRepository = Depends(get_document_repo),
    s3: S3Client = Depends(get_s3_client),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    filename = file.filename or "untitled"
    ext = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""

    supported = _default_registry.supported_extensions
    if ext and ext not in supported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(supported))}",
        )

    data = await file.read()
    file_size = len(data)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_size_mb} MB limit",
        )

    file_hash = hashlib.sha256(data).hexdigest()
    existing = await document_repo.get_by_hash(file_hash)
    if existing is not None and existing.status in ("queued", "processing", "completed"):
        return UploadResponse.model_validate(existing)

    s3_key = f"documents/{uuid4()}/{filename}"
    await s3.upload(data, s3_key)

    doc = await document_repo.create(
        DocumentCreate(
            filename=filename,
            file_type=ext.lstrip("."),
            file_size=file_size,
            file_hash=file_hash,
            s3_key=s3_key,
            strategy=strategy,
        )
    )

    queue = rq.Queue(settings.redis_queue_name, connection=redis)
    queue.enqueue("backend.workers.jobs.process_document", str(doc.id))

    return UploadResponse.model_validate(doc)


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
