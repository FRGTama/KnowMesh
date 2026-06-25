from sentence_transformers import SentenceTransformer

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(text: str) -> list[float]:
    if not text.strip():
        return [0.0] * 384
    return _get_model().encode(text).tolist()


def generate_response(contexts: list[str], query: str) -> str:
    if not contexts:
        return "No relevant information found in the provided materials."
    context_section = "\n\n".join(contexts)
    return (
        f"Based on the provided materials:\n\n"
        f"{context_section}\n\n"
        f"---\n\n"
        f"In response to: {query}"
    )
