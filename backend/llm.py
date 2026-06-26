import os

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

_embedding_model = None
_openai_client = None
_deepseek_client = None

EMBED_MODEL="all-MiniLM-L6-v2"

def _get_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBED_MODEL)
    return _embedding_model


def embed(text: str) -> list[float]:
    if not text.strip():
        return [0.0] * 384
    return _get_model().encode(text).tolist()


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_client


def _get_deepseek_client():
    global _deepseek_client
    if _deepseek_client is None:
        from openai import OpenAI
        _deepseek_client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1",
        )
    return _deepseek_client

def _get_llm_client(provider: str):
    # TODO: abstract the llm client selection procedure, maybe abstract to an Object Client() +provider +model
    if provider == "deepseek":
        client = _get_deepseek_client()
    else:
        client = _get_openai_client()
    return client


def generate_response(contexts: list[str], query: str, provider: str = "openai", model: str = "gpt4.0") -> str:
    if not contexts:
        return "No relevant information found in the provided materials."
    if provider == "none":
        context_section = "\n\n".join(contexts)
        return (
            f"Based on the provided materials:\n\n"
            f"{context_section}\n\n"
            f"---\n\n"
            f"In response to: {query}"
        )

    system_prompt = (
        "You are a helpful study assistant. Answer the user's question based solely "
        "on the provided context materials. If the context does not contain enough "
        "information to answer, say so."
    )
    context_block = "\n\n".join(contexts)
    user_prompt = f"Context materials:\n{context_block}\n\nQuestion: {query}"

    client = _get_llm_client(provider)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()
