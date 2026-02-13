"""End-to-end tests for REPL mode with real workflows."""

from unittest.mock import AsyncMock, patch

import pytest

from pisti.agents.base import BaseAgent
from pisti.cli.repl import run_interactive_session
from pisti.core.types import AgentResult, LLMResponse, Message
from pisti.tools.base import ToolRegistry


class MockLLMForREPL:
    """Mock LLM for REPL testing."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def chat(self, messages, tools=None):
        if self._call_count >= len(self._responses):
            # Default response if we run out
            return LLMResponse(
                message=Message(role="assistant", content="Default response")
            )
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp

    async def chat_stream(self, messages, tools=None):
        if self._call_count >= len(self._responses):
            yield LLMResponse(
                message=Message(role="assistant", content="Default response"),
                done=True,
            )
            return

        resp = self._responses[self._call_count]
        self._call_count += 1

        if resp.message.content:
            yield LLMResponse(
                message=Message(role="assistant", content=resp.message.content),
                model=resp.model,
                done=False,
            )

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


class StubAgent(BaseAgent):
    def _build_initial_messages(self, instruction):
        return [
            Message(role="system", content="Test agent."),
            Message(role="user", content=instruction),
        ]


@pytest.mark.asyncio
async def test_repl_multi_turn_conversation():
    """Test full multi-turn REPL conversation."""
    llm = MockLLMForREPL([
        LLMResponse(message=Message(role="assistant", content="First response")),
        LLMResponse(message=Message(role="assistant", content="Second response")),
        LLMResponse(message=Message(role="assistant", content="Third response")),
    ])

    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    with patch("pisti.cli.repl.Prompt.ask", side_effect=[
        "follow up 1",
        "follow up 2",
        "exit",
    ]):
        await run_interactive_session(
            agent=agent,
            initial_instruction="initial request",
            console=console,
        )

    # Verify agent was called 3 times
    assert agent._messages is not None
    # Should have: system, user (initial), assistant,
    # user (follow1), assistant, user (follow2), assistant
    user_messages = [m for m in agent._messages if m.role == "user"]
    assert len(user_messages) == 3
    assert user_messages[0].content == "initial request"
    assert user_messages[1].content == "follow up 1"
    assert user_messages[2].content == "follow up 2"


@pytest.mark.asyncio
async def test_repl_eof_error():
    """Test REPL handles EOF (Ctrl+D) gracefully."""
    llm = MockLLMForREPL([])
    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    with patch("pisti.cli.repl.Prompt.ask", side_effect=EOFError()):
        await run_interactive_session(
            agent=agent,
            initial_instruction=None,
            console=console,
        )

    # Should exit gracefully without calling agent
    assert len(agent._messages) == 0


@pytest.mark.asyncio
async def test_repl_exception_recovery():
    """Test REPL recovers from agent exceptions."""
    llm = MockLLMForREPL([
        # First call will raise error (simulated by agent)
        LLMResponse(message=Message(role="assistant", content="Success after error")),
    ])

    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    call_count = 0

    async def mock_run(instruction, continue_session=False):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("Agent error")
        return AgentResult(summary="Success after error", iterations=1)

    agent.run = mock_run

    with patch("pisti.cli.repl.Prompt.ask", side_effect=[
        "instruction that fails",
        "instruction that works",
        "exit",
    ]):
        await run_interactive_session(
            agent=agent,
            initial_instruction=None,
            console=console,
        )

    # Verify error was printed
    console.print.assert_any_call(
        "[bold red]Error:[/bold red] Agent error"
    )

    # Verify second call succeeded
    assert call_count == 2


@pytest.mark.asyncio
async def test_repl_empty_initial_instruction():
    """Test REPL with empty initial instruction prompts immediately."""
    llm = MockLLMForREPL([
        LLMResponse(message=Message(role="assistant", content="Response")),
    ])

    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    with patch("pisti.cli.repl.Prompt.ask", side_effect=["first prompt", "exit"]):
        await run_interactive_session(
            agent=agent,
            initial_instruction="",
            console=console,
        )

    # Verify agent was called with the prompted instruction
    user_messages = [m for m in agent._messages if m.role == "user"]
    assert len(user_messages) == 1
    assert user_messages[0].content == "first prompt"


@pytest.mark.asyncio
async def test_repl_whitespace_initial_instruction():
    """Test REPL with whitespace-only initial instruction."""
    llm = MockLLMForREPL([
        LLMResponse(message=Message(role="assistant", content="Response")),
    ])

    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    with patch("pisti.cli.repl.Prompt.ask", side_effect=["real instruction", "exit"]):
        await run_interactive_session(
            agent=agent,
            initial_instruction="   ",
            console=console,
        )

    # Whitespace-only should be treated as empty
    user_messages = [m for m in agent._messages if m.role == "user"]
    assert len(user_messages) == 1
    assert user_messages[0].content == "real instruction"


@pytest.mark.asyncio
async def test_repl_case_insensitive_exit():
    """Test REPL accepts EXIT, exit, QUIT, quit."""
    llm = MockLLMForREPL([])
    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    # Test with uppercase EXIT
    with patch("pisti.cli.repl.Prompt.ask", return_value="EXIT"):
        await run_interactive_session(agent=agent, console=console)

    assert len(agent._messages) == 0

    # Test with mixed case Quit
    agent._messages = []
    with patch("pisti.cli.repl.Prompt.ask", return_value="Quit"):
        await run_interactive_session(agent=agent, console=console)

    assert len(agent._messages) == 0


@pytest.mark.asyncio
async def test_repl_skip_multiple_empty_inputs():
    """Test REPL skips multiple empty inputs in a row."""
    llm = MockLLMForREPL([
        LLMResponse(message=Message(role="assistant", content="Response")),
    ])

    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    with patch("pisti.cli.repl.Prompt.ask", side_effect=[
        "",
        "  ",
        "\t",
        "actual instruction",
        "exit",
    ]):
        await run_interactive_session(agent=agent, console=console)

    # Only the actual instruction should have been processed
    user_messages = [m for m in agent._messages if m.role == "user"]
    assert len(user_messages) == 1
    assert user_messages[0].content == "actual instruction"


@pytest.mark.asyncio
async def test_repl_displays_welcome_panel():
    """Test REPL displays welcome message."""
    from rich.panel import Panel

    llm = MockLLMForREPL([])
    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    with patch("pisti.cli.repl.Prompt.ask", return_value="exit"):
        await run_interactive_session(agent=agent, console=console)

    # Verify console.print was called with a Panel object
    console.print.assert_called()
    # Check that first call was with a Panel
    first_call = console.print.call_args_list[0]
    assert isinstance(first_call[0][0], Panel)
    # Check that Panel contains welcome text
    panel_content = str(first_call[0][0].renderable)
    assert "Interactive Mode" in panel_content or "interactive" in panel_content.lower()


@pytest.mark.asyncio
async def test_repl_displays_exit_message():
    """Test REPL displays exit message when leaving."""
    llm = MockLLMForREPL([])
    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    with patch("pisti.cli.repl.Prompt.ask", return_value="exit"):
        await run_interactive_session(agent=agent, console=console)

    # Verify exit message was printed
    console.print.assert_any_call("[dim]Exiting interactive mode.[/dim]")


@pytest.mark.asyncio
async def test_repl_displays_interrupt_message():
    """Test REPL displays interrupt message on Ctrl+C."""
    llm = MockLLMForREPL([])
    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    with patch("pisti.cli.repl.Prompt.ask", side_effect=KeyboardInterrupt()):
        await run_interactive_session(agent=agent, console=console)

    # Verify interrupt message was printed
    console.print.assert_any_call("\n[dim]Interrupted. Exiting interactive mode.[/dim]")


@pytest.mark.asyncio
async def test_repl_session_continuity():
    """Test that REPL maintains session continuity across turns."""
    llm = MockLLMForREPL([
        LLMResponse(message=Message(role="assistant", content="Created file.py")),
        LLMResponse(message=Message(role="assistant", content="Added tests")),
        LLMResponse(message=Message(role="assistant", content="Added docs")),
    ])

    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    with patch("pisti.cli.repl.Prompt.ask", side_effect=[
        "add tests",
        "add documentation",
        "exit",
    ]):
        await run_interactive_session(
            agent=agent,
            initial_instruction="create file.py",
            console=console,
        )

    # Verify all interactions are in message history
    messages = agent._messages
    assert len(messages) > 0

    # Check that assistant responses accumulated
    assistant_messages = [m for m in messages if m.role == "assistant"]
    assert len(assistant_messages) == 3
    assert assistant_messages[0].content == "Created file.py"
    assert assistant_messages[1].content == "Added tests"
    assert assistant_messages[2].content == "Added docs"


@pytest.mark.asyncio
async def test_repl_with_event_handler():
    """Test REPL with RichEventHandler produces formatted output."""
    from pisti.cli.ui import RichEventHandler

    llm = MockLLMForREPL([
        LLMResponse(message=Message(role="assistant", content="Response text")),
    ])

    registry = ToolRegistry()
    console = AsyncMock()
    handler = RichEventHandler(console=console)
    agent = StubAgent(llm=llm, tool_registry=registry, event_handler=handler)

    with patch("pisti.cli.repl.Prompt.ask", side_effect=["test", "exit"]):
        await run_interactive_session(
            agent=agent,
            initial_instruction=None,
            console=console,
        )

    # Event handler should have been triggered
    # (This is a bit indirect, but we can check that console was used)
    assert console.print.call_count > 0


@pytest.mark.asyncio
async def test_repl_long_session():
    """Test REPL with many turns (stress test)."""
    # Create 20 responses
    responses = [
        LLMResponse(message=Message(role="assistant", content=f"Response {i}"))
        for i in range(20)
    ]

    llm = MockLLMForREPL(responses)
    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    # 20 instructions + exit
    instructions = [f"instruction {i}" for i in range(20)] + ["exit"]

    with patch("pisti.cli.repl.Prompt.ask", side_effect=instructions):
        await run_interactive_session(agent=agent, console=console)

    # Verify all 20 turns were processed
    user_messages = [m for m in agent._messages if m.role == "user"]
    assert len(user_messages) == 20


@pytest.mark.asyncio
async def test_repl_prompt_formatting():
    """Test that REPL prompt is properly formatted."""
    llm = MockLLMForREPL([])
    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    with patch("pisti.cli.repl.Prompt.ask", return_value="exit") as mock_ask:
        await run_interactive_session(agent=agent, console=console)

    # Verify Prompt.ask was called with formatted prompt
    mock_ask.assert_called()
    call_args = mock_ask.call_args
    prompt_text = call_args[0][0]
    assert "You" in prompt_text or "you" in prompt_text.lower()


@pytest.mark.asyncio
async def test_repl_initial_instruction_not_none_uses_first_turn():
    """Test that providing initial instruction uses it for first turn."""
    llm = MockLLMForREPL([
        LLMResponse(message=Message(role="assistant", content="Initial response")),
    ])

    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    with patch("pisti.cli.repl.Prompt.ask", return_value="exit") as mock_ask:
        await run_interactive_session(
            agent=agent,
            initial_instruction="do something",
            console=console,
        )

    # Prompt should only be called once (for after initial instruction)
    assert mock_ask.call_count == 1

    # Agent should have been called with initial instruction
    user_messages = [m for m in agent._messages if m.role == "user"]
    assert len(user_messages) == 1
    assert user_messages[0].content == "do something"


@pytest.mark.asyncio
async def test_repl_continue_session_flag_progression():
    """Test that continue_session flag is False for first turn, True for subsequent."""
    llm = MockLLMForREPL([
        LLMResponse(message=Message(role="assistant", content="Response 1")),
        LLMResponse(message=Message(role="assistant", content="Response 2")),
    ])

    registry = ToolRegistry()
    agent = StubAgent(llm=llm, tool_registry=registry)
    console = AsyncMock()

    # Track the continue_session parameter
    run_calls = []
    original_run = agent.run

    async def tracked_run(instruction, continue_session=False):
        run_calls.append(
            {"instruction": instruction, "continue_session": continue_session}
        )
        return await original_run(instruction, continue_session=continue_session)

    agent.run = tracked_run

    with patch("pisti.cli.repl.Prompt.ask", side_effect=["second turn", "exit"]):
        await run_interactive_session(
            agent=agent,
            initial_instruction="first turn",
            console=console,
        )

    # Verify the continue_session progression
    assert len(run_calls) == 2
    assert run_calls[0]["continue_session"] is False  # First turn
    assert run_calls[1]["continue_session"] is True   # Second turn
