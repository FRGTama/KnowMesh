from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Document:
    text: str
    metadata: dict = field(default_factory=dict)


def load(path: str) -> list[Document]:
    path_obj = Path(path)
    ext = path_obj.suffix.lower()
    base_metadata = {"filename": path_obj.name, "path": str(path_obj.absolute())}

    if not path_obj.exists():
        return [Document(text="", metadata={**base_metadata, "error": "File not found"})]

    loader = _LOADERS.get(ext)
    if loader is None:
        return [Document(
            text=f"[Unsupported file type: {ext}. Supported: .txt, .pdf]",
            metadata={**base_metadata, "error": f"Loader not implemented for {ext}"},
        )]
    return loader(path_obj, base_metadata)


def _load_text(path: Path, base_metadata: dict) -> list[Document]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if not text:
        return [Document(text="", metadata={**base_metadata, "page": 0, "error": "Empty file"})]
    return [Document(text=text, metadata={**base_metadata, "page": 0})]


def _load_pdf(path: Path, base_metadata: dict) -> list[Document]:
    import pymupdf
    doc = pymupdf.open(path)
    documents = []
    for i, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            documents.append(Document(
                text=text,
                metadata={**base_metadata, "page": i, "total_pages": len(doc)},
            ))
    doc.close()
    if not documents:
        return [Document(text="", metadata={**base_metadata, "error": "No extractable text in PDF"})]
    return documents


_LOADERS = {
    ".txt": _load_text,
    ".pdf": _load_pdf,
}
