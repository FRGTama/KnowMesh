import os
import tempfile
from pathlib import Path

import pytest

from backend.rag.ingestion.document_loader import (
    LiteParseLoader,
    LoaderRegistry,
    TextLoader,
    load,
)


class TestTextLoader:
    def test_load_text(self):
        loader = TextLoader()
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write("Hello world")
        f.close()
        docs = loader.load(Path(f.name), {"filename": "test.txt"})
        os.unlink(f.name)
        assert len(docs) == 1
        assert docs[0].text == "Hello world"

    def test_empty_file(self):
        loader = TextLoader()
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write("")
        f.close()
        docs = loader.load(Path(f.name), {"filename": "empty.txt"})
        os.unlink(f.name)
        assert len(docs) == 1
        assert docs[0].text == ""
        assert "error" in docs[0].metadata

    def test_document_id_passthrough(self):
        loader = TextLoader()
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write("hello")
        f.close()
        docs = loader.load(Path(f.name), {"filename": "test.txt", "document_id": "abc123"})
        os.unlink(f.name)
        assert docs[0].metadata.get("document_id") == "abc123"


class TestLiteParseLoader:
    def test_load_pdf(self):
        try:
            import fitz
        except ImportError:
            pytest.skip("pymupdf not installed")
        loader = LiteParseLoader()
        doc = fitz.open()
        doc.new_page().insert_text((50, 50), "PDF page 1")
        doc.new_page().insert_text((50, 50), "PDF page 2")
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.close()
        doc.save(tmp.name)
        doc.close()
        docs = loader.load(Path(tmp.name), {"filename": "test.pdf", "document_id": "pdf1"})
        os.unlink(tmp.name)
        assert len(docs) == 2
        for d in docs:
            assert d.metadata.get("document_id") == "pdf1"

    def test_load_pdf_no_text(self):
        try:
            import fitz
        except ImportError:
            pytest.skip("pymupdf not installed")
        loader = LiteParseLoader()
        doc = fitz.open()
        doc.new_page()
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.close()
        doc.save(tmp.name)
        doc.close()
        docs = loader.load(Path(tmp.name), {"filename": "blank.pdf"})
        os.unlink(tmp.name)
        assert len(docs) >= 1
        assert "error" in docs[0].metadata or docs[0].text == ""


class TestLoaderRegistry:
    def test_register_and_get(self):
        registry = LoaderRegistry()
        registry.register(".txt", TextLoader())
        assert registry.get_loader(".txt") is not None
        assert registry.get_loader(".pdf") is None

    def test_supported_extensions(self):
        registry = LoaderRegistry()
        registry.register(".txt", TextLoader())
        registry.register(".pdf", LiteParseLoader())
        assert ".txt" in registry.supported_extensions
        assert ".pdf" in registry.supported_extensions

    def test_lowercase_normalisation(self):
        registry = LoaderRegistry()
        registry.register(".TXT", TextLoader())
        assert registry.get_loader(".txt") is not None


class TestLoadFunction:
    def test_load_txt_with_document_id(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write("hello")
        f.close()
        docs = load(f.name, document_id="uid1")
        os.unlink(f.name)
        assert len(docs) == 1
        assert docs[0].metadata.get("document_id") == "uid1"

    def test_load_nonexistent_file(self):
        docs = load("/nonexistent/file.txt")
        assert "error" in docs[0].metadata

    def test_load_unsupported_extension(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False)
        f.write("hello")
        f.close()
        docs = load(f.name)
        os.unlink(f.name)
        assert "error" in docs[0].metadata
        assert "Unsupported" in docs[0].text

    def test_custom_registry(self):
        registry = LoaderRegistry()
        registry.register(".txt", TextLoader())
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write("custom")
        f.close()
        docs = load(f.name, document_id="custom", registry=registry)
        os.unlink(f.name)
        assert docs[0].metadata.get("document_id") == "custom"
