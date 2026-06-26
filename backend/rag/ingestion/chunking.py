from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import tiktoken

from backend.rag.ingestion.document_loader import Document


_ENCODING = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    text: str
    doc_id: str
    index: int
    strategy: str
    metadata: dict = field(default_factory=dict)


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, document: Document) -> list[Chunk]:
        ...


class RecursiveChunker(BaseChunker):
    def __init__(self, window_size: int = 512, overlap: int = 128):
        if overlap >= window_size:
            raise ValueError("overlap must be smaller than window_size")
        self.window_size = window_size
        self.overlap = overlap

    def chunk(self, document: Document) -> list[Chunk]:
        tokens = _ENCODING.encode(document.text)
        if not tokens:
            return []

        chunks = []
        start = 0
        index = 0
        while start < len(tokens):
            end = min(start + self.window_size, len(tokens))
            chunk_text = _ENCODING.decode(tokens[start:end])
            chunks.append(Chunk(
                text=chunk_text,
                doc_id=document.metadata.get("filename", "unknown"),
                index=index,
                strategy="recursive",
                metadata={**document.metadata},
            ))
            index += 1
            if end == len(tokens):
                break
            start += self.window_size - self.overlap
        return chunks


class SemanticChunker(BaseChunker):
    def __init__(self, window_size: int = 512):
        self.window_size = window_size
        # TODO: asbtract the fallback strategy selection
        self._fallback = RecursiveChunker(window_size=window_size, overlap=0)

    def chunk(self, document: Document) -> list[Chunk]:
        paragraphs = [p.strip() for p in document.text.split("\n\n") if p.strip()]
        if not paragraphs:
            return []

        chunks = []
        index = 0
        for para in paragraphs:
            if self._exceeds_window(para):
                fallback_doc = Document(text=para, metadata=document.metadata)
                for chunk in self._fallback.chunk(fallback_doc):
                    chunk.index = index
                    chunk.strategy = "recursive_fallback_semantic"
                    chunks.append(chunk)
                    index += 1
            else:
                chunks.append(Chunk(
                    text=para,
                    doc_id=document.metadata.get("filename", "unknown"),
                    index=index,
                    strategy="semantic",
                    metadata={**document.metadata},
                ))
                index += 1
        return chunks

    def _exceeds_window(self, text: str) -> bool:
        return len(_ENCODING.encode(text)) > self.window_size
