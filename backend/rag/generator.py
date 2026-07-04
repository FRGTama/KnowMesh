from pathlib import Path

from backend.app.core.llm_manager import LLMManager

PROMPT_DIR = Path(__file__).parent.parent / "prompts"

def load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")



class Generator:
    def __init__(self, manager: LLMManager):
        self._manager = manager

    async def generate(
        self,
        query: str,
        contexts: list[str],
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        system_prompt = load_prompt("system/rag_generator.md")
        context_block = "\n\n".join(contexts)
        user_prompt = f"Context materials:\n{context_block}\n\nQuestion: {query}"
        return await self._manager.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
