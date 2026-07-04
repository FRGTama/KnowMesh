"""Graph layer for entity/relation storage and graph-assisted retrieval.

Backed by PostgreSQL (entities, relations, chunk_entities tables).
"""

from backend.rag.graph.service import GraphService

__all__ = ["GraphService"]
