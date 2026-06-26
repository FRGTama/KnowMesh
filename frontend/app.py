import sys
from pathlib import Path
import tempfile
import uuid
import uvicorn

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.rag.ingestion.pipeline import process_file as _ingest, count_store, clear_store
from backend.rag.agents.retrieval_agent import ask as _ask


app = FastAPI(title="KnowMesh")


FRONTEND_DIST = Path(__file__).parent / "dist"


@app.post("/upload")
async def upload(file: UploadFile = File(...), strategy: str = Form("recursive")):
    suffix = Path(file.filename).suffix if file.filename else ".txt"
    tmp_path = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}{suffix}"
    content = await file.read()
    tmp_path.write_bytes(content)
    try:
        _ingest(str(tmp_path), strategy)
    finally:
        tmp_path.unlink(missing_ok=True)
    return JSONResponse({"ok": True, "filename": file.filename})


@app.post("/query")
async def query(query: str = Form(...), provider: str = Form("openai"), model: str = Form("gpt4.0")):
    answer = _ask(query, provider=provider, model=model)
    return JSONResponse({"answer": answer})


@app.get("/collection-info")
async def collection_info():
    return JSONResponse({"name": "student_rag", "count": count_store()})


@app.post("/clear")
async def clear():
    count = clear_store()
    return JSONResponse({"cleared": True, "count": count})


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app="frontend.app:app", host="127.0.0.1", port=8000, reload=True)
