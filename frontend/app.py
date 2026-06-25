import sys
from pathlib import Path
import tempfile
import uuid

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.rag.ingestion.pipeline import process_file as _ingest
from backend.rag.agents.retrieval_agent import ask as _ask


app = FastAPI(title="Student RAG Assistant")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, answer: str = ""):
    return templates.TemplateResponse("index.html", {"request": request, "answer": answer})


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
    return RedirectResponse(url="/", status_code=303)


@app.post("/query")
async def query(request: Request, query: str = Form(...)):
    answer = _ask(query)
    return templates.TemplateResponse("index.html", {"request": request, "answer": answer})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("frontend.app:app", host="127.0.0.1", port=8000, reload=True)