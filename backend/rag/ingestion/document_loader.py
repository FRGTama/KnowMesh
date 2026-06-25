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
        return [Document(
            text="",
            metadata={**base_metadata, "error": "File not found"},
        )]

    if ext == ".txt":
        return _load_text(path_obj, base_metadata)

    return [Document(
        text=f"[Unsupported file type: {ext}. Only .txt is supported in MVP.]",
        metadata={**base_metadata, "error": f"Loader not implemented for {ext}"},
    )]


def _load_text(path: Path, base_metadata: dict) -> list[Document]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if not text:
        return [Document(
            text="",
            metadata={**base_metadata, "page": 0, "error": "Empty file"},
        )]
    return [Document(
        text=text,
        metadata={**base_metadata, "page": 0},
    )]
