"""End-to-end tests for interactive CLI features with streaming."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from pisti.cli.app import app
from pisti.core.types import (
    AgentResult,
    FunctionCall,
    LLMResponse,
    Message,
    ToolCall,
)

runner = CliRunner()


class MockStreamingLLM:
    """Mock LLM that simulates streaming behavior."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def chat(self, messages, tools=None):
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp

    async def chat_stream(self, messages, tools=None):
        """Stream responses token by token."""
        resp = self._responses[self._call_count]
        self._call_count += 1

        # Stream content as tokens if present
        if resp.message.content:
            # Simulate streaming by breaking into tokens
            words = resp.message.content.split()
            for i, word in enumerate(words):
                token = word if i == len(words) - 1 else word + " "
                yield LLMResponse(
                    message=Message(role="assistant", content=token),
                    model=resp.model,
                    done=False,
                )

        # Final chunk with tool calls
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


@pytest.mark.asyncio
async def test_cli_streaming_output():
    """Test that CLI streams LLM output when using event handler."""
    from pisti.agents.base import BaseAgent
    from pisti.cli.ui import RichEventHandler
    from pisti.tools.base import ToolRegistry

    llm = MockStreamingLLM([
        LLMResponse(message=Message(role="assistant", content="Creating the file now"))
    ])

    class StubAgent(BaseAgent):
        def _build_initial_messages(self, instruction):
            return [Message(role="user", content=instruction)]

    registry = ToolRegistry()
    handler = RichEventHandler()
    agent = StubAgent(llm=llm, tool_registry=registry, event_handler=handler)

    # Verify streaming is triggered
    result = await agent.run("test instruction")
    assert result.summary == "Creating the file now"
    assert result.iterations == 1


def test_cli_code_command_with_streaming():
    """Test code command invokes streaming through RichEventHandler."""
    mock_result = AgentResult(
        summary="File created successfully",
        files_modified=["test.py"],
        iterations=1,
    )

    with patch("pisti.cli.app._build_coder_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = mock_result
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)

        result = runner.invoke(app, ["code", "Create test.py"])

        assert result.exit_code == 0
        # Verify agent was called
        mock_agent.run.assert_called_once()
        call_args = mock_agent.run.call_args
        assert call_args[0][0] == "Create test.py"


def test_cli_interactive_flag_triggers_repl():
    """Test that --interactive flag triggers REPL mode."""
    with patch("pisti.cli.app._build_coder_agent") as mock_build, \
         patch("pisti.cli.repl.run_interactive_session") as mock_repl:

        mock_agent = AsyncMock()
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)
        mock_repl.return_value = None

        result = runner.invoke(
            app,
            ["code", "--interactive", "Initial instruction"],
        )

        assert result.exit_code == 0
        # Verify REPL was called instead of direct run
        mock_repl.assert_called_once()
        call_args = mock_repl.call_args
        assert call_args[1]["agent"] == mock_agent
        assert call_args[1]["initial_instruction"] == "Initial instruction"


def test_cli_interactive_short_flag():
    """Test that -i flag works as alias for --interactive."""
    with patch("pisti.cli.app._build_coder_agent") as mock_build, \
         patch("pisti.cli.repl.run_interactive_session") as mock_repl:

        mock_agent = AsyncMock()
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)
        mock_repl.return_value = None

        result = runner.invoke(
            app,
            ["code", "-i", "Test instruction"],
        )

        assert result.exit_code == 0
        mock_repl.assert_called_once()


def test_cli_non_interactive_shows_instruction_panel():
    """Test that non-interactive mode shows instruction panel."""
    with patch("pisti.cli.app._build_coder_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(summary="Done", iterations=1)
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)

        result = runner.invoke(app, ["code", "Create test.py"])

        assert result.exit_code == 0
        # Check that instruction panel is shown (contains "Instruction")
        assert "Instruction" in result.output or "Create test.py" in result.output


def test_cli_interactive_no_instruction_panel():
    """Test that interactive mode doesn't show instruction panel."""
    with patch("pisti.cli.app._build_coder_agent") as mock_build, \
         patch("pisti.cli.repl.run_interactive_session") as mock_repl:

        mock_agent = AsyncMock()
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)
        mock_repl.return_value = None

        result = runner.invoke(app, ["code", "-i", "Test"])

        assert result.exit_code == 0
        # Interactive mode should not show the instruction panel
        # (REPL will handle its own UI)
        mock_repl.assert_called_once()
        assert "Instruction" not in result.output
@pytest.mark.asyncio
async def test_streaming_with_tool_calls():
    """Test streaming output followed by tool calls."""
    from pisti.agents.base import BaseAgent
    from pisti.cli.ui import RichEventHandler
    from pisti.tools.base import BaseTool, ToolRegistry

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

    llm = MockStreamingLLM([
        # First response with tool call
        LLMResponse(
            message=Message(
                role="assistant",
                content="I will use the echo tool",
                tool_calls=[
                    ToolCall(
                        id="t1",
                        function=FunctionCall(name="echo", arguments={"text": "hello"}),
                    )
                ],
            )
        ),
        # Final response
        LLMResponse(
            message=Message(role="assistant", content="Tool executed successfully")
        ),
    ])

    class StubAgent(BaseAgent):
        def _build_initial_messages(self, instruction):
            return [Message(role="user", content=instruction)]

    registry = ToolRegistry()
    registry.register(EchoTool())
    handler = RichEventHandler()
    agent = StubAgent(llm=llm, tool_registry=registry, event_handler=handler)

    result = await agent.run("use echo")
    assert result.summary == "Tool executed successfully"
    assert result.iterations == 2


@pytest.mark.asyncio
async def test_streaming_empty_content_with_tools():
    """Test streaming when LLM returns only tool calls (no text content)."""
    from pisti.agents.base import BaseAgent
    from pisti.cli.ui import RichEventHandler
    from pisti.tools.base import BaseTool, ToolRegistry

    class DummyTool(BaseTool):
        @property
        def name(self):
            return "dummy"

        @property
        def description(self):
            return "A dummy tool"

        @property
        def parameters(self):
            return {"type": "object", "properties": {}}

        async def execute(self, **kwargs):
            return "dummy result"

    llm = MockStreamingLLM([
        # Response with NO content, only tool call
        LLMResponse(
            message=Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        id="t1",
                        function=FunctionCall(name="dummy", arguments={}),
                    )
                ],
            )
        ),
        LLMResponse(message=Message(role="assistant", content="Done")),
    ])

    class StubAgent(BaseAgent):
        def _build_initial_messages(self, instruction):
            return [Message(role="user", content=instruction)]

    registry = ToolRegistry()
    registry.register(DummyTool())
    handler = RichEventHandler()
    agent = StubAgent(llm=llm, tool_registry=registry, event_handler=handler)

    result = await agent.run("test")
    assert result.summary == "Done"
    assert result.iterations == 2


@pytest.mark.asyncio
async def test_streaming_very_long_output():
    """Test streaming with very long output (stress test)."""
    from pisti.agents.base import BaseAgent
    from pisti.cli.ui import RichEventHandler
    from pisti.tools.base import ToolRegistry

    # Create a very long response
    long_text = " ".join([f"word{i}" for i in range(1000)])

    llm = MockStreamingLLM([
        LLMResponse(message=Message(role="assistant", content=long_text))
    ])

    class StubAgent(BaseAgent):
        def _build_initial_messages(self, instruction):
            return [Message(role="user", content=instruction)]

    registry = ToolRegistry()
    handler = RichEventHandler()
    agent = StubAgent(llm=llm, tool_registry=registry, event_handler=handler)

    result = await agent.run("test")
    assert result.summary == long_text
    assert "word0" in result.summary
    assert "word999" in result.summary


@pytest.mark.asyncio
async def test_error_during_streaming():
    """Test error handling during streaming."""
    from pisti.agents.base import BaseAgent
    from pisti.cli.ui import RichEventHandler
    from pisti.tools.base import ToolRegistry

    class FailingLLM:
        async def chat(self, messages, tools=None):
            raise RuntimeError("LLM connection failed")

        async def chat_stream(self, messages, tools=None):
            yield LLMResponse(
                message=Message(role="assistant", content="Starting..."),
                done=False,
            )
            raise RuntimeError("Streaming interrupted")

        async def close(self):
            pass

    class StubAgent(BaseAgent):
        def _build_initial_messages(self, instruction):
            return [Message(role="user", content=instruction)]

    registry = ToolRegistry()
    handler = RichEventHandler()
    agent = StubAgent(llm=FailingLLM(), tool_registry=registry, event_handler=handler)

    with pytest.raises(RuntimeError, match="Streaming interrupted"):
        await agent.run("test")


def test_cli_error_handling_connection_error():
    """Test CLI handles LLM connection errors gracefully."""
    from pisti.core.errors import LLMConnectionError

    with patch("pisti.cli.app._build_coder_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = LLMConnectionError("Cannot reach Ollama")
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)

        result = runner.invoke(app, ["code", "Test instruction"])

        assert result.exit_code == 1
        assert "Connection error" in result.output or "Cannot reach" in result.output


def test_cli_error_handling_general_error():
    """Test CLI handles general Pisti errors gracefully."""
    from pisti.core.errors import PistiError

    with patch("pisti.cli.app._build_coder_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = PistiError("Something went wrong")
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)

        result = runner.invoke(app, ["code", "Test instruction"])

        assert result.exit_code == 1
        assert "Error" in result.output


def test_cli_provider_cleanup():
    """Test that LLM provider is properly closed after execution."""
    with patch("pisti.cli.app._build_coder_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(summary="Done", iterations=1)
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)

        result = runner.invoke(app, ["code", "Test"])

        assert result.exit_code == 0
        # Verify provider was closed
        mock_provider.close.assert_called_once()


def test_cli_provider_cleanup_on_error():
    """Test that provider is closed even when an error occurs."""
    from pisti.core.errors import PistiError

    with patch("pisti.cli.app._build_coder_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = PistiError("Error")
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)

        result = runner.invoke(app, ["code", "Test"])

        assert result.exit_code == 1
        # Verify provider was still closed
        mock_provider.close.assert_called_once()


@pytest.mark.asyncio
async def test_continue_session_preserves_context():
    """Test that continue_session=True preserves message history."""
    from pisti.agents.base import BaseAgent
    from pisti.tools.base import ToolRegistry

    llm = MockStreamingLLM([
        LLMResponse(message=Message(role="assistant", content="First response")),
        LLMResponse(message=Message(role="assistant", content="Second response")),
    ])

    class StubAgent(BaseAgent):
        def _build_initial_messages(self, instruction):
            return [
                Message(role="system", content="System prompt"),
                Message(role="user", content=instruction),
            ]

    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)

    # First call
    result1 = await agent.run("First instruction")
    assert result1.summary == "First response"
    initial_msg_count = len(agent._messages)

    # Second call with continue_session
    result2 = await agent.run("Second instruction", continue_session=True)
    assert result2.summary == "Second response"

    # Verify messages accumulated
    assert len(agent._messages) > initial_msg_count
    # Check that user message was added
    user_messages = [m for m in agent._messages if m.role == "user"]
    assert len(user_messages) == 2
    assert user_messages[0].content == "First instruction"
    assert user_messages[1].content == "Second instruction"


@pytest.mark.asyncio
async def test_continue_session_false_resets_context():
    """Test that continue_session=False resets message history."""
    from pisti.agents.base import BaseAgent
    from pisti.tools.base import ToolRegistry

    llm = MockStreamingLLM([
        LLMResponse(message=Message(role="assistant", content="First response")),
        LLMResponse(message=Message(role="assistant", content="Second response")),
    ])

    class StubAgent(BaseAgent):
        def _build_initial_messages(self, instruction):
            return [
                Message(role="system", content="System prompt"),
                Message(role="user", content=instruction),
            ]

    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)

    # First call
    await agent.run("First instruction")
    first_msg_count = len(agent._messages)

    # Second call without continue_session (default False)
    await agent.run("Second instruction")

    # Message count should be reset to similar level
    # (system + user + assistant for second call)
    assert len(agent._messages) <= first_msg_count + 1

    # Should only have one user message (the new one)
    user_messages = [m for m in agent._messages if m.role == "user"]
    assert len(user_messages) == 1
    assert user_messages[0].content == "Second instruction"


@pytest.mark.asyncio
async def test_continue_session_resets_files_modified():
    """Test that continue_session=False resets files_modified tracking."""
    from pisti.agents.base import BaseAgent
    from pisti.tools.base import BaseTool, ToolRegistry
    from pisti.tools.filesystem import ToolOutput

    class FileTool(BaseTool):
        @property
        def name(self):
            return "write"

        @property
        def description(self):
            return "Writes a file"

        @property
        def parameters(self):
            return {"type": "object"}

        async def execute(self, **kwargs):
            return ToolOutput(
                content="Written",
                metadata={"files_modified": ["test.py"]}
            )

    llm = MockStreamingLLM([
        LLMResponse(
            message=Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        id="t1",
                        function=FunctionCall(name="write", arguments={}),
                    )
                ],
            )
        ),
        LLMResponse(message=Message(role="assistant", content="Done 1")),
        LLMResponse(message=Message(role="assistant", content="Done 2")),
    ])

    class StubAgent(BaseAgent):
        def _build_initial_messages(self, instruction):
            return [Message(role="user", content=instruction)]

    registry = ToolRegistry()
    registry.register(FileTool())
    agent = StubAgent(llm=llm, tool_registry=registry)

    # First call modifies a file
    result1 = await agent.run("write file")
    assert "test.py" in result1.files_modified

    # Second call without continue_session should reset
    result2 = await agent.run("second instruction", continue_session=False)
    assert result2.files_modified == []


def test_cli_with_model_option():
    """Test CLI with custom model option."""
    with patch("pisti.cli.app._build_coder_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(summary="Done", iterations=1)
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)

        result = runner.invoke(
            app,
            ["code", "--model", "llama3.2:1b", "Test instruction"],
        )

        assert result.exit_code == 0
        # Verify build was called with correct model
        call_args = mock_build.call_args
        assert call_args[1]["model"] == "llama3.2:1b"


def test_cli_with_directory_option():
    """Test CLI with custom working directory."""
    with patch("pisti.cli.app._build_coder_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(summary="Done", iterations=1)
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)

        test_dir = Path("/tmp/test")
        result = runner.invoke(
            app,
            ["code", "--dir", str(test_dir), "Test instruction"],
        )

        assert result.exit_code == 0
        # Verify build was called with correct directory
        call_args = mock_build.call_args
        assert call_args[1]["working_dir"] == test_dir


def test_cli_verbose_flag():
    """Test CLI with verbose flag."""
    with patch("pisti.cli.app._build_coder_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentResult(summary="Done", iterations=1)
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)

        result = runner.invoke(
            app,
            ["code", "--verbose", "Test instruction"],
        )

        assert result.exit_code == 0
        # Verify build was called with verbose=True
        call_args = mock_build.call_args
        assert call_args[1]["verbose"] is True
