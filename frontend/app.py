import sys
import tempfile
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.rag.agents.retrieval_agent import ask as _ask
from backend.rag.ingestion.pipeline import Pipeline
from backend.rag.registry import FileStorage, SqliteRegistry

app = FastAPI(title="KnowMesh")
FRONTEND_DIST = Path(__file__).parent / "dist"


REGISTRY_DB = str(Path(__file__).resolve().parent.parent / "data" / "registry.db")
STORAGE_DIR = str(Path(__file__).resolve().parent.parent / "data" / "storage")

_registry = SqliteRegistry(REGISTRY_DB)
_storage = FileStorage(STORAGE_DIR)
_pipeline = Pipeline(registry=_registry, storage=_storage)


@app.post("/upload")
async def upload(file: UploadFile = File(...), strategy: str = Form("recursive")):
    suffix = Path(file.filename).suffix if file.filename else ".txt"
    tmp_path = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}{suffix}"
    content = await file.read()
    tmp_path.write_bytes(content)
    try:
        document_id = _pipeline.process_file(str(tmp_path), strategy)
    finally:
        tmp_path.unlink(missing_ok=True)
    return JSONResponse({"ok": True, "filename": file.filename, "document_id": document_id})


@app.post("/query")
async def query(
    query: str = Form(...),
    provider: str = Form("openai"),
    model: str = Form("gpt4.0"),
    document_ids: str = Form(""),
):
    ids = [d.strip() for d in document_ids.split(",") if d.strip()] or None
    answer = _ask(_pipeline, query, provider=provider, model=model, document_ids=ids)
    return JSONResponse({"answer": answer})


@app.get("/collection-info")
async def collection_info():
    return JSONResponse({"name": "student_rag", "count": _pipeline.count_store()})


@app.post("/clear")
async def clear():
    count = _pipeline.clear_store()
    return JSONResponse({"cleared": True, "count": count})


@app.get("/documents")
async def list_documents():
    docs = _pipeline.list_documents()
    return JSONResponse([
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "total_pages": d.total_pages,
            "tags": d.tags,
            "created_at": d.created_at,
        }
        for d in docs
    ])


@app.get("/documents/{document_id}")
async def get_document(document_id: str):
    doc = _pipeline.get_document(document_id)
    if doc is None:
        return JSONResponse({"error": "Document not found"}, status_code=404)
    return JSONResponse({
        "id": doc.id,
        "filename": doc.filename,
        "source_path": doc.source_path,
        "file_type": doc.file_type,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "total_pages": doc.total_pages,
        "strategy": doc.strategy,
        "tags": doc.tags,
        "error": doc.error,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    })


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    doc = _pipeline.get_document(document_id)
    if doc is None:
        return JSONResponse({"error": "Document not found"}, status_code=404)
    chunk_count = _pipeline.delete_document(document_id)
    return JSONResponse({"deleted": True, "document_id": document_id, "chunk_count": chunk_count})


class _PatchDoc(BaseModel):
    tags: list[str]


@app.patch("/documents/{document_id}")
async def patch_document(document_id: str, body: _PatchDoc):
    doc = _pipeline.get_document(document_id)
    if doc is None:
        return JSONResponse({"error": "Document not found"}, status_code=404)
    _registry.update_document(document_id, tags=body.tags)
    return JSONResponse({"ok": True, "tags": body.tags})


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app="frontend.app:app", host="127.0.0.1", port=8000, reload=True)
