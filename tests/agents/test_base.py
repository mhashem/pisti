"""Tests for base agent."""


import pytest

from pisti.agents.base import BaseAgent
from pisti.core.errors import MaxIterationsError
from pisti.core.types import (
    FunctionCall,
    LLMResponse,
    Message,
    ToolCall,
)
from pisti.llm.base import LLMProvider
from pisti.tools.base import BaseTool, ToolRegistry


class MockLLM(LLMProvider):
    """LLM that returns pre-configured responses in sequence."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def chat(self, messages, tools=None):
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp

    async def chat_stream(self, messages, tools=None):
        yield self._responses[0]  # type: ignore

    async def close(self):
        pass


class EchoTool(BaseTool):
    @property
    def name(self):
        return "echo"

    @property
    def description(self):
        return "Echoes input"

    @property
    def parameters(self):
        return {"type": "object", "properties": {"text": {"type": "string"}}}

    async def execute(self, **kwargs):
        return f"Echo: {kwargs.get('text', '')}"


class StubAgent(BaseAgent):
    def _build_initial_messages(self, instruction):
        return [
            Message(role="system", content="You are a test agent."),
            Message(role="user", content=instruction),
        ]


@pytest.mark.asyncio
async def test_agent_final_answer():
    llm = MockLLM(
        [
            LLMResponse(message=Message(role="assistant", content="All done!")),
        ]
    )
    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    result = await agent.run("do something")
    assert result.summary == "All done!"
    assert result.iterations == 1


@pytest.mark.asyncio
async def test_agent_tool_call_then_answer():
    llm = MockLLM(
        [
            LLMResponse(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ToolCall(
                            id="t1",
                            function=FunctionCall(
                                name="echo", arguments={"text": "hi"}
                            ),
                        )
                    ],
                )
            ),
            LLMResponse(
                message=Message(role="assistant", content="Done after tool call.")
            ),
        ]
    )
    registry = ToolRegistry()
    registry.register(EchoTool())
    agent = StubAgent(llm=llm, tool_registry=registry)
    result = await agent.run("use echo")
    assert result.summary == "Done after tool call."
    assert result.iterations == 2


@pytest.mark.asyncio
async def test_agent_unknown_tool():
    llm = MockLLM(
        [
            LLMResponse(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ToolCall(
                            id="t1",
                            function=FunctionCall(name="nonexistent", arguments={}),
                        )
                    ],
                )
            ),
            LLMResponse(message=Message(role="assistant", content="Handled error.")),
        ]
    )
    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    result = await agent.run("call bad tool")
    assert result.summary == "Handled error."


@pytest.mark.asyncio
async def test_agent_max_iterations():
    # Always returns tool calls, never a final answer
    responses = [
        LLMResponse(
            message=Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        id=f"t{i}",
                        function=FunctionCall(name="echo", arguments={"text": "loop"}),
                    )
                ],
            )
        )
        for i in range(5)
    ]
    llm = MockLLM(responses)
    registry = ToolRegistry()
    registry.register(EchoTool())
    agent = StubAgent(llm=llm, tool_registry=registry, max_iterations=3)
    with pytest.raises(MaxIterationsError):
        await agent.run("loop forever")
