import shutil
from pathlib import Path


class FileStorage:
    def __init__(self, base_path: str):
        self._base = Path(base_path)

    def save(self, document_id: str, filename: str, content: bytes) -> str:
        dest = self._base / document_id / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return str(dest)

    def get_path(self, document_id: str, filename: str) -> Path:
        return self._base / document_id / filename

    def delete(self, document_id: str) -> None:
        shutil.rmtree(self._base / document_id, ignore_errors=True)
