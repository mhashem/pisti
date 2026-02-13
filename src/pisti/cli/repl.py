"""Interactive REPL for multi-turn agent sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

if TYPE_CHECKING:
    from pisti.agents.base import BaseAgent


async def run_interactive_session(
    agent: BaseAgent,
    initial_instruction: str | None = None,
    console: Console | None = None,
) -> None:
    """Run an interactive REPL session with the agent."""
    console = console or Console()

    console.print(
        Panel(
            "[bold cyan]Interactive Mode[/bold cyan]\n"
            "Type your instructions below. Type 'exit' or 'quit' to leave.\n"
            "Press Ctrl+C or Ctrl+D to abort.",
            expand=False,
        )
    )

    instruction = initial_instruction
    first_turn = True

    while True:
        try:
            if instruction is None or not instruction.strip():
                instruction = Prompt.ask("\n[bold blue]You[/bold blue]")

            if instruction.strip().lower() in ("exit", "quit"):
                console.print("[dim]Exiting interactive mode.[/dim]")
                break

            if not instruction.strip():
                instruction = None
                continue

            await agent.run(instruction, continue_session=not first_turn)
            first_turn = False
            instruction = None

        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Interrupted. Exiting interactive mode.[/dim]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            instruction = None
