"""Integration test: full agent loop with mock LLM writing a file."""

from pathlib import Path

import pytest

from pisti.agents.coder import CoderAgent
from pisti.core.types import FunctionCall, LLMResponse, Message, ToolCall
from pisti.tools.base import ToolRegistry
from pisti.tools.filesystem import (
    ListDirectoryTool,
    ReadFileTool,
    WriteFileTool,
)
from tests.agents.test_base import MockLLM


@pytest.mark.asyncio
async def test_full_loop_creates_file(tmp_path: Path):
    """Mock LLM lists dir, writes a file, then gives final answer."""
    llm = MockLLM(
        [
            # Step 1: LLM calls list_directory
            LLMResponse(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ToolCall(
                            id="t1",
                            function=FunctionCall(
                                name="list_directory", arguments={"path": "."}
                            ),
                        )
                    ],
                )
            ),
            # Step 2: LLM writes hello.py
            LLMResponse(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ToolCall(
                            id="t2",
                            function=FunctionCall(
                                name="write_file",
                                arguments={
                                    "path": "hello.py",
                                    "content": 'print("Hello, world!")\n',
                                },
                            ),
                        )
                    ],
                )
            ),
            # Step 3: Final answer
            LLMResponse(
                message=Message(
                    role="assistant",
                    content="Created hello.py with a hello world script.",
                )
            ),
        ]
    )

    registry = ToolRegistry()
    registry.register(ReadFileTool(base_dir=tmp_path))
    registry.register(WriteFileTool(base_dir=tmp_path))
    registry.register(ListDirectoryTool(base_dir=tmp_path))

    agent = CoderAgent(
        llm=llm,
        tool_registry=registry,
        working_dir=tmp_path,
    )

    result = await agent.run("Create a hello world script")

    # Verify result
    assert "hello.py" in result.summary
    assert "hello.py" in result.files_modified
    assert result.iterations == 3

    # Verify file actually exists on disk
    created = tmp_path / "hello.py"
    assert created.exists()
    assert 'print("Hello, world!")' in created.read_text()
