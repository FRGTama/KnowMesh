from dataclasses import dataclass, field

from backend.rag.ingestion.chunking import Chunk
from backend.llm import embed as _embed


@dataclass
class EmbeddedChunk(Chunk):
    vector: list[float] = field(default_factory=list)


def embed_chunks(chunks: list[Chunk]) -> list[EmbeddedChunk]:
    if not chunks:
        return []
    return [
        EmbeddedChunk(
            text=c.text,
            doc_id=c.doc_id,
            index=c.index,
            strategy=c.strategy,
            metadata={**c.metadata},
            vector=_embed(c.text),
        )
        for c in chunks
    ]
