from backend.rag.ingestion.pipeline import process_query
from backend.llm import generate_response


def ask(query: str, top_k: int = 5, provider: str = "openai", model: str = "gpt4.0") -> str:
    results = process_query(query, top_k)
    contexts = [r["text"] for r in results]
    return generate_response(contexts, query, provider=provider, model=model)

def rerank():
    #TODO: implement agentic re-ranker with graph, calculator and
    pass