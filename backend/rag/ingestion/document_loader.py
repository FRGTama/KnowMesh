from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from liteparse import LiteParse


@dataclass
class Document:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentLoader(ABC):
    @abstractmethod
    def load(self, path: Path, base_metadata: dict[str, Any]) -> list[Document]:
        ...


class TextLoader(DocumentLoader):
    def load(self, path: Path, base_metadata: dict[str, Any]) -> list[Document]:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if not text:
            return [Document(text="", metadata={**base_metadata, "error": "Empty file"})]
        return [Document(text=text, metadata={**base_metadata})]


class LiteParseLoader(DocumentLoader):
    def load(self, path: Path, base_metadata: dict[str, Any]) -> list[Document]:
        parser = LiteParse(output_format="text")
        result = parser.parse(str(path))
        documents = []
        for page in result.pages:
            text = page.text.strip()
            if text:
                documents.append(Document(
                    text=text,
                    metadata={
                        **base_metadata,
                        "page": page.page_num - 1,
                        "total_pages": len(result.pages),
                    },
                ))
        if not documents:
            return [Document(text="", metadata={**base_metadata, "error": "No extractable text"})]
        return documents


class LoaderRegistry:
    def __init__(self) -> None:
        self._loaders: dict[str, DocumentLoader] = {}

    def register(self, extension: str, loader: DocumentLoader) -> None:
        self._loaders[extension.lower()] = loader

    def get_loader(self, extension: str) -> DocumentLoader | None:
        return self._loaders.get(extension.lower())

    @property
    def supported_extensions(self) -> list[str]:
        return list(self._loaders.keys())


def _create_default_registry() -> LoaderRegistry:
    registry = LoaderRegistry()
    registry.register(".txt", TextLoader())
    liteparse_extensions = [".pdf", ".docx", ".doc", ".pptx", ".ppt", ".png", ".jpg", ".jpeg"]
    liteparse_loader = LiteParseLoader()
    for ext in liteparse_extensions:
        registry.register(ext, liteparse_loader)
    return registry


_default_registry = _create_default_registry()


def load(
    path: str,
    document_id: str = "",
    registry: LoaderRegistry | None = None,
) -> list[Document]:
    r = registry or _default_registry
    path_obj = Path(path)
    ext = path_obj.suffix.lower()
    base_metadata = {
        "filename": path_obj.name,
        "path": str(path_obj.absolute()),
        "file_type": ext,
        "document_id": document_id,
    }

    if not path_obj.exists():
        return [Document(text="", metadata={**base_metadata, "error": "File not found"})]

    loader = r.get_loader(ext)
    if loader is None:
        return [Document(
            text=f"[Unsupported file type: {ext}. Supported: {', '.join(r.supported_extensions)}]",
            metadata={**base_metadata, "error": f"Loader not implemented for {ext}"},
        )]
    return loader.load(path_obj, base_metadata)
