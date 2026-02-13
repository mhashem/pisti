"""Pisti CLI application."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel

from pisti.core.config import load_config
from pisti.core.errors import LLMConnectionError, PistiError

app = typer.Typer(
    name="pisti",
    help="Multi-agent SDLC platform.",
    no_args_is_help=True,
)
config_app = typer.Typer(help="Configuration commands.")
app.add_typer(config_app, name="config")

console = Console()


def _build_coder_agent(
    model: str | None = None,
    working_dir: Path | None = None,
    verbose: bool = False,
    event_handler: Any = None,
) -> tuple[Any, Any]:
    """Wire up dependencies and return (agent, provider)."""
    from pisti.agents.coder import CoderAgent
    from pisti.core.config import load_config
    from pisti.llm.ollama import OllamaProvider
    from pisti.tools.base import ToolRegistry
    from pisti.tools.filesystem import (
        ListDirectoryTool,
        ReadFileTool,
        SearchFilesTool,
        WriteFileTool,
    )

    cfg = load_config()
    work_dir = working_dir or Path.cwd()
    model_name = model or cfg.agents.coder.model

    provider = OllamaProvider(
        base_url=cfg.ollama.base_url,
        model=model_name,
        timeout=cfg.ollama.timeout,
    )

    registry = ToolRegistry()
    registry.register(ReadFileTool(base_dir=work_dir))
    registry.register(WriteFileTool(base_dir=work_dir))
    registry.register(ListDirectoryTool(base_dir=work_dir))
    registry.register(SearchFilesTool(base_dir=work_dir))

    agent = CoderAgent(
        llm=provider,
        tool_registry=registry,
        working_dir=work_dir,
        max_iterations=cfg.agents.coder.max_iterations,
        context_window=cfg.agents.coder.context_window,
        verbose=verbose,
        event_handler=event_handler,
    )

    return agent, provider


@app.command()
def code(
    instruction: Annotated[str, typer.Argument(help="What to build or change.")],
    dir: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help="Working directory."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Ollama model to use."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed output."),
    ] = False,
    interactive: Annotated[
        bool,
        typer.Option("--interactive", "-i", help="Run in interactive REPL mode."),
    ] = False,
) -> None:
    """Run the Coder agent on an instruction."""
    from pisti.cli.repl import run_interactive_session
    from pisti.cli.ui import RichEventHandler

    if not interactive:
        console.print(
            Panel(instruction, title="[bold blue]Instruction[/bold blue]", expand=False)
        )

    handler = RichEventHandler(console=console)
    agent, provider = _build_coder_agent(
        model=model,
        working_dir=dir,
        verbose=verbose,
        event_handler=handler,
    )

    async def _run() -> None:
        try:
            if interactive:
                await run_interactive_session(
                    agent=agent,
                    initial_instruction=instruction,
                    console=console,
                )
            else:
                await agent.run(instruction)
        except LLMConnectionError as e:
            console.print(f"[bold red]Connection error:[/bold red] {e}")
            raise typer.Exit(1)
        except PistiError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)
        finally:
            await provider.close()

    asyncio.run(_run())


@config_app.command("init")
def config_init(
    dir: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help="Directory for .pisti/config.yaml."),
    ] = None,
) -> None:
    """Create a default .pisti/config.yaml."""
    target_dir = (dir or Path.cwd()) / ".pisti"
    target_dir.mkdir(parents=True, exist_ok=True)
    config_path = target_dir / "config.yaml"

    if config_path.exists():
        console.print(f"[yellow]Config already exists:[/yellow] {config_path}")
        return

    cfg = load_config()
    import yaml

    config_path.write_text(yaml.dump(cfg.model_dump(), default_flow_style=False))
    console.print(f"[green]Created:[/green] {config_path}")
