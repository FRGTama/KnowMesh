import os
import tempfile
from pathlib import Path

import pytest

from backend.rag.registry import DocumentRecord, FileStorage, SqliteRegistry


@pytest.fixture
def registry():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    reg = SqliteRegistry(f.name)
    yield reg
    reg.close()
    os.unlink(f.name)


@pytest.fixture
def storage():
    path = tempfile.mkdtemp()
    fs = FileStorage(path)
    yield fs


class TestRegistry:
    def test_create_and_get(self, registry):
        registry.create_document(DocumentRecord(
            id="d1", filename="a.txt", source_path="/a.txt",
            file_type=".txt", status="processing",
        ))
        doc = registry.get_document("d1")
        assert doc is not None
        assert doc.id == "d1"
        assert doc.filename == "a.txt"
        assert doc.status == "processing"

    def test_get_missing(self, registry):
        assert registry.get_document("nonexistent") is None

    def test_update(self, registry):
        registry.create_document(DocumentRecord(
            id="d1", filename="a.txt", source_path="/a.txt",
            file_type=".txt", status="processing",
        ))
        registry.update_document("d1", status="completed", chunk_count=5)
        doc = registry.get_document("d1")
        assert doc.status == "completed"
        assert doc.chunk_count == 5

    def test_list(self, registry):
        registry.create_document(DocumentRecord(
            id="d1", filename="a.txt", source_path="/a.txt",
            file_type=".txt", status="completed",
        ))
        registry.create_document(DocumentRecord(
            id="d2", filename="b.pdf", source_path="/b.pdf",
            file_type=".pdf", status="failed", error="bad file",
        ))
        docs = registry.list_documents()
        assert len(docs) == 2
        ids = {d.id for d in docs}
        assert ids == {"d1", "d2"}

    def test_delete(self, registry):
        registry.create_document(DocumentRecord(
            id="d1", filename="a.txt", source_path="/a.txt",
            file_type=".txt", status="completed",
        ))
        registry.delete_document("d1")
        assert registry.get_document("d1") is None

    def test_tags_roundtrip(self, registry):
        registry.create_document(DocumentRecord(
            id="d1", filename="a.txt", source_path="/a.txt",
            file_type=".txt", status="completed",
            tags=["lecture", "math"],
        ))
        doc = registry.get_document("d1")
        assert doc.tags == ["lecture", "math"]

        registry.update_document("d1", tags=["physics"])
        doc = registry.get_document("d1")
        assert doc.tags == ["physics"]


class TestFileStorage:
    def test_save_and_get(self, storage):
        path = storage.save("doc1", "hello.txt", b"hello world")
        assert Path(path).exists()
        assert Path(path).read_text() == "hello world"
        assert storage.get_path("doc1", "hello.txt").exists()

    def test_delete(self, storage):
        storage.save("doc1", "hello.txt", b"hello")
        storage.delete("doc1")
        assert not storage.get_path("doc1", "hello.txt").exists()
