from backend.llm import generate_response
from backend.rag.ingestion.pipeline import Pipeline


def ask(
    pipeline: Pipeline,
    query: str,
    top_k: int = 5,
    provider: str = "openai",
    model: str = "gpt4.0",
    document_ids: list[str] | None = None,
) -> str:
    results = pipeline.process_query(query, top_k, document_ids=document_ids)
    contexts = [r["text"] for r in results]
    return generate_response(contexts, query, provider=provider, model=model)
