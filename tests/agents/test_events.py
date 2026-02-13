"""Tests for event handler protocol."""

import pytest

from pisti.agents.base import BaseAgent
from pisti.agents.events import AgentEventHandler, NullEventHandler
from pisti.core.types import (
    FunctionCall,
    LLMResponse,
    Message,
    ToolCall,
    ToolResult,
)
from pisti.llm.base import LLMProvider
from pisti.tools.base import BaseTool, ToolRegistry


class MockLLM(LLMProvider):
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def chat(self, messages, tools=None):
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp

    async def chat_stream(self, messages, tools=None):
        resp = self._responses[self._call_count]
        self._call_count += 1
        # For streaming, yield the content as tokens if available
        if resp.message.content:
            # Yield the content as a single token
            yield LLMResponse(
                message=Message(role="assistant", content=resp.message.content),
                model=resp.model,
                done=False,
            )
        # Then yield the final response with tool_calls
        yield LLMResponse(
            message=Message(
                role="assistant",
                content="",
                tool_calls=resp.message.tool_calls,
            ),
            model=resp.model,
            done=resp.done,
        )

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


class RecordingEventHandler:
    """Records all events for verification."""

    def __init__(self):
        self.events = []

    def on_agent_start(self, agent_name: str, instruction: str) -> None:
        self.events.append(("agent_start", agent_name, instruction))

    def on_agent_end(
        self, summary: str, files_modified: list[str], iterations: int
    ) -> None:
        self.events.append(("agent_end", summary, files_modified, iterations))

    def on_iteration_start(self, iteration: int, max_iterations: int) -> None:
        self.events.append(("iteration_start", iteration, max_iterations))

    def on_llm_start(self) -> None:
        self.events.append(("llm_start",))

    def on_token(self, token: str) -> None:
        self.events.append(("token", token))

    def on_llm_end(self, content: str) -> None:
        self.events.append(("llm_end", content))

    def on_tool_start(self, tool_call: ToolCall) -> None:
        self.events.append(("tool_start", tool_call.function.name))

    def on_tool_end(self, tool_call: ToolCall, result: ToolResult) -> None:
        self.events.append(("tool_end", tool_call.function.name, result.content))

    def on_error(self, error: Exception) -> None:
        self.events.append(("error", str(error)))


@pytest.mark.asyncio
async def test_null_event_handler_is_default():
    """NullEventHandler is used when no handler is provided."""
    llm = MockLLM([LLMResponse(message=Message(role="assistant", content="Done!"))])
    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)

    assert isinstance(agent.event_handler, NullEventHandler)
    result = await agent.run("test")
    assert result.summary == "Done!"


@pytest.mark.asyncio
async def test_event_sequence_final_answer():
    """Events are emitted in correct order for final answer."""
    llm = MockLLM([LLMResponse(message=Message(role="assistant", content="All done!"))])
    registry = ToolRegistry()
    handler = RecordingEventHandler()
    agent = StubAgent(llm=llm, tool_registry=registry, event_handler=handler)

    result = await agent.run("do something")

    assert result.summary == "All done!"
    # With non-null handler, streaming is used, which emits llm_start, token, llm_end
    assert handler.events == [
        ("agent_start", "StubAgent", "do something"),
        ("iteration_start", 1, 20),
        ("llm_start",),
        ("token", "All done!"),
        ("llm_end", "All done!"),
        ("agent_end", "All done!", [], 1),
    ]


@pytest.mark.asyncio
async def test_event_sequence_with_tool_call():
    """Events are emitted in correct order with tool calls."""
    llm = MockLLM([
        LLMResponse(
            message=Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        id="t1",
                        function=FunctionCall(name="echo", arguments={"text": "hi"}),
                    )
                ],
            )
        ),
        LLMResponse(message=Message(role="assistant", content="Done after tool.")),
    ])
    registry = ToolRegistry()
    registry.register(EchoTool())
    handler = RecordingEventHandler()
    agent = StubAgent(llm=llm, tool_registry=registry, event_handler=handler)

    result = await agent.run("use echo")

    assert result.summary == "Done after tool."
    # With streaming: iteration 1 has no content (tool calls only),
    # iteration 2 has content
    assert handler.events == [
        ("agent_start", "StubAgent", "use echo"),
        ("iteration_start", 1, 20),
        ("llm_start",),
        ("llm_end", ""),
        ("tool_start", "echo"),
        ("tool_end", "echo", "Echo: hi"),
        ("iteration_start", 2, 20),
        ("llm_start",),
        ("token", "Done after tool."),
        ("llm_end", "Done after tool."),
        ("agent_end", "Done after tool.", [], 2),
    ]


@pytest.mark.asyncio
async def test_event_handler_protocol():
    """AgentEventHandler is a runtime checkable protocol."""
    handler = RecordingEventHandler()
    assert isinstance(handler, AgentEventHandler)

    null_handler = NullEventHandler()
    assert isinstance(null_handler, AgentEventHandler)
