from unittest.mock import AsyncMock

import pytest

from backend.app.core.llm_manager import LLMManager
from backend.rag.generator import Generator
from tests.utils import make_test_settings


@pytest.mark.asyncio
async def test_generator_builds_prompt_and_delegates():
    manager = LLMManager(settings=make_test_settings())
    manager.generate = AsyncMock(return_value="Generated answer")

    generator = Generator(manager)
    answer = await generator.generate("What is X?", ["context one", "context two"])

    assert answer == "Generated answer"
    call_args = manager.generate.await_args.kwargs
    assert "What is X?" in call_args["user_prompt"]
    assert "context one" in call_args["user_prompt"]
    assert "context two" in call_args["user_prompt"]
    assert "study assistant" in call_args["system_prompt"]
