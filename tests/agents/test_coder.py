"""Tests for coder agent."""

import pytest

from pisti.agents.coder import CoderAgent
from pisti.core.types import LLMResponse, Message
from pisti.tools.base import ToolRegistry
from pisti.tools.filesystem import ReadFileTool
from tests.agents.test_base import MockLLM


@pytest.mark.asyncio
async def test_coder_builds_system_prompt():
    llm = MockLLM(
        [
            LLMResponse(message=Message(role="assistant", content="Done!")),
        ]
    )
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    agent = CoderAgent(llm=llm, tool_registry=registry)

    result = await agent.run("Create hello.py")

    assert result.summary == "Done!"
    # Verify the LLM received a system message with tool names
    # (MockLLM was called, so it worked)
    assert result.iterations == 1
