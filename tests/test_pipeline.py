import os
import tempfile
from unittest.mock import ANY, MagicMock

import pytest

from backend.rag.ingestion.pipeline import Pipeline
from backend.rag.ingestion.store import VectorStore
from backend.rag.registry import DocumentRecord, FileStorage, SqliteRegistry


class TestPipeline:
    def setup_method(self):
        self.reg = MagicMock(spec=SqliteRegistry)
        self.storage = MagicMock(spec=FileStorage)
        self.store = MagicMock(spec=VectorStore)
        self.store.delete_by_document_id.return_value = 0
        self.pipeline = Pipeline(registry=self.reg, storage=self.storage, store=self.store)

    def test_process_file_creates_registry_entry(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write("test content")
        f.close()

        doc_id = self.pipeline.process_file(f.name)
        os.unlink(f.name)

        assert doc_id is not None
        self.reg.create_document.assert_called_once()
        call_args = self.reg.create_document.call_args[0][0]
        assert call_args.id == doc_id
        assert call_args.filename.endswith(".txt")
        assert call_args.status == "processing"

        self.store.upsert.assert_called_once()
        self.reg.update_document.assert_called_once_with(
            doc_id, status="completed", chunk_count=1, total_pages=0, strategy="recursive"
        )

    def test_process_file_with_tags(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write("test")
        f.close()

        self.pipeline.process_file(f.name, tags=["math", "lecture"])
        os.unlink(f.name)

        call_args = self.reg.create_document.call_args[0][0]
        assert call_args.tags == ["math", "lecture"]

    def test_process_file_failure_updates_status(self):
        self.store.upsert.side_effect = RuntimeError("embedding failed")
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write("test")
        f.close()

        with pytest.raises(RuntimeError):
            self.pipeline.process_file(f.name)
        os.unlink(f.name)

        self.reg.update_document.assert_called_with(
            ANY, status="failed", error=ANY
        )

    def test_process_query_passes_document_ids(self):
        self.store.search.return_value = [{"text": "result", "metadata": {}}]
        results = self.pipeline.process_query("hello", top_k=3, document_ids=["d1"])
        self.store.search.assert_called_with(ANY, 3, document_ids=["d1"])
        assert len(results) == 1

    def test_process_query_all_docs(self):
        self.store.search.return_value = [{"text": "result", "metadata": {}}]
        results = self.pipeline.process_query("hello")
        self.store.search.assert_called_with(ANY, 5, document_ids=None)
        assert len(results) == 1

    def test_delete_document(self):
        self.reg.get_document.return_value = DocumentRecord(
            id="d1", filename="a.txt", source_path="/a",
            file_type=".txt", status="completed",
        )
        self.store.delete_by_document_id.return_value = 3

        deleted = self.pipeline.delete_document("d1")
        assert deleted == 3
        self.store.delete_by_document_id.assert_called_with("d1")
        self.storage.delete.assert_called_with("d1")
        self.reg.delete_document.assert_called_with("d1")

    def test_clear_store(self):
        self.reg.list_documents.return_value = [
            DocumentRecord(id="d1", filename="a.txt", source_path="/a", file_type=".txt", status="completed"),
        ]
        self.store.clear.return_value = 5

        count = self.pipeline.clear_store()
        assert count == 5
        self.storage.delete.assert_called_with("d1")
        self.reg.delete_document.assert_called_with("d1")

