from backend.rag.ingestion.chunking import RecursiveChunker, SemanticChunker
from backend.rag.ingestion.document_loader import Document


def test_recursive_chunker_short():
    doc = Document(text="Hello world", metadata={"filename": "test.txt", "document_id": "d1"})
    chunks = RecursiveChunker(window_size=512, overlap=0).chunk(doc)
    assert len(chunks) == 1
    assert chunks[0].doc_id == "d1"
    assert chunks[0].index == 0
    assert chunks[0].strategy == "recursive"


def test_recursive_chunker_splits():
    text = "word " * 600
    doc = Document(text=text, metadata={"filename": "test.txt", "document_id": "d1"})
    chunks = RecursiveChunker(window_size=512, overlap=0).chunk(doc)
    assert len(chunks) >= 2
    assert all(c.strategy == "recursive" for c in chunks)
    assert {c.doc_id for c in chunks} == {"d1"}
    indices = [c.index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_recursive_chunker_overlap():
    doc = Document(text="word " * 600, metadata={"filename": "test.txt", "document_id": "d1"})
    no_overlap = RecursiveChunker(window_size=256, overlap=0).chunk(doc)
    with_overlap = RecursiveChunker(window_size=256, overlap=128).chunk(doc)
    assert len(with_overlap) > len(no_overlap)


def test_semantic_chunker_single_paragraph():
    doc = Document(text="Hello world", metadata={"filename": "test.txt", "document_id": "d1"})
    chunks = SemanticChunker(window_size=512).chunk(doc)
    assert len(chunks) == 1
    assert chunks[0].strategy == "semantic"


def test_semantic_chunker_multi_paragraph():
    doc = Document(text="Para one.\n\nPara two.\n\nPara three.", metadata={"filename": "test.txt", "document_id": "d1"})
    chunks = SemanticChunker(window_size=512).chunk(doc)
    assert len(chunks) == 3
    assert all(c.strategy == "semantic" for c in chunks)


def test_semantic_chunker_long_paragraph_fallback():
    text = "word " * 1000
    doc = Document(text=text, metadata={"filename": "test.txt", "document_id": "d1"})
    chunks = SemanticChunker(window_size=512).chunk(doc)
    assert len(chunks) >= 2
    assert all(c.strategy == "recursive_fallback_semantic" for c in chunks)


def test_empty_document():
    doc = Document(text="", metadata={"filename": "empty.txt", "document_id": "d1"})
    assert RecursiveChunker().chunk(doc) == []
    assert SemanticChunker().chunk(doc) == []


def test_chunk_metadata_contains_document_id():
    doc = Document(text="Hello", metadata={"filename": "test.txt", "document_id": "uid1"})
    chunks = RecursiveChunker().chunk(doc)
    assert chunks[0].metadata["document_id"] == "uid1"
    assert chunks[0].doc_id == "uid1"
