"""Tests for REPL functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pisti.agents.base import BaseAgent
from pisti.cli.repl import run_interactive_session
from pisti.core.types import AgentResult, Message


class StubAgent(BaseAgent):
    def _build_initial_messages(self, instruction):
        return [
            Message(role="system", content="Test agent."),
            Message(role="user", content=instruction),
        ]


@pytest.mark.asyncio
async def test_repl_exit_command():
    """REPL exits on 'exit' command."""
    agent = MagicMock(spec=BaseAgent)
    agent.run = AsyncMock(return_value=AgentResult(summary="Done", iterations=1))

    console = MagicMock()

    with patch("pisti.cli.repl.Prompt.ask", side_effect=["exit"]):
        await run_interactive_session(agent, initial_instruction=None, console=console)

    agent.run.assert_not_called()


@pytest.mark.asyncio
async def test_repl_quit_command():
    """REPL exits on 'quit' command."""
    agent = MagicMock(spec=BaseAgent)
    agent.run = AsyncMock(return_value=AgentResult(summary="Done", iterations=1))

    console = MagicMock()

    with patch("pisti.cli.repl.Prompt.ask", side_effect=["quit"]):
        await run_interactive_session(agent, initial_instruction=None, console=console)

    agent.run.assert_not_called()


@pytest.mark.asyncio
async def test_repl_initial_instruction():
    """REPL runs initial instruction without prompting."""
    agent = MagicMock(spec=BaseAgent)
    agent.run = AsyncMock(return_value=AgentResult(summary="Done", iterations=1))

    console = MagicMock()

    with patch("pisti.cli.repl.Prompt.ask", side_effect=["exit"]):
        await run_interactive_session(
            agent, initial_instruction="create hello.py", console=console
        )

    agent.run.assert_called_once()
    call_args = agent.run.call_args
    assert call_args[0][0] == "create hello.py"
    assert call_args[1]["continue_session"] is False


@pytest.mark.asyncio
async def test_repl_continue_session():
    """REPL uses continue_session=True for follow-up instructions."""
    agent = MagicMock(spec=BaseAgent)
    agent.run = AsyncMock(return_value=AgentResult(summary="Done", iterations=1))

    console = MagicMock()

    with patch(
        "pisti.cli.repl.Prompt.ask",
        side_effect=["add tests", "exit"],
    ):
        await run_interactive_session(
            agent, initial_instruction="create hello.py", console=console
        )

    assert agent.run.call_count == 2
    first_call = agent.run.call_args_list[0]
    second_call = agent.run.call_args_list[1]

    assert first_call[0][0] == "create hello.py"
    assert first_call[1]["continue_session"] is False

    assert second_call[0][0] == "add tests"
    assert second_call[1]["continue_session"] is True


@pytest.mark.asyncio
async def test_repl_keyboard_interrupt():
    """REPL handles KeyboardInterrupt gracefully."""
    agent = MagicMock(spec=BaseAgent)
    console = MagicMock()

    with patch("pisti.cli.repl.Prompt.ask", side_effect=KeyboardInterrupt()):
        await run_interactive_session(agent, initial_instruction=None, console=console)

    # Should exit without error
    agent.run.assert_not_called()


@pytest.mark.asyncio
async def test_repl_empty_input():
    """REPL ignores empty input and prompts again."""
    agent = MagicMock(spec=BaseAgent)
    agent.run = AsyncMock(return_value=AgentResult(summary="Done", iterations=1))

    console = MagicMock()

    with patch("pisti.cli.repl.Prompt.ask", side_effect=["", "  ", "exit"]):
        await run_interactive_session(agent, initial_instruction=None, console=console)

    agent.run.assert_not_called()
