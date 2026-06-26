from dataclasses import dataclass, field

from backend.llm import embed as _embed
from backend.rag.ingestion.chunking import Chunk


@dataclass
class EmbeddedChunk(Chunk):
    vector: list[float] = field(default_factory=list)

# TODO: embed references
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
