"""Rich-based event handler for CLI output."""

from __future__ import annotations

import time

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from pisti.core.types import ToolCall, ToolResult

# Tool style map: (icon, color)
_TOOL_STYLES: dict[str, tuple[str, str]] = {
    "read_file": ("\U0001f4d6", "blue"),
    "write_file": ("\u270f\ufe0f ", "green"),
    "list_directory": ("\U0001f4c1", "yellow"),
    "search_files": ("\U0001f50d", "magenta"),
}

_DEFAULT_TOOL_STYLE = ("\u2699\ufe0f ", "cyan")


class RichEventHandler:
    """Streams agent output with Claude Code / Gemini-inspired styling."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self._live: Live | None = None
        self._token_buffer: str = ""
        self._start_time: float = 0.0

    def on_agent_start(self, agent_name: str, instruction: str) -> None:
        self.console.print()
        self.console.print(
            Text(f"\u25cf {agent_name}", style="bold bright_cyan")
        )
        self._start_time = time.monotonic()

    def on_agent_end(
        self, summary: str, files_modified: list[str], iterations: int
    ) -> None:
        if files_modified:
            file_lines = "\n".join(f"  + {f}" for f in sorted(files_modified))
            self.console.print(
                Panel(
                    file_lines,
                    title="[bold green]Files Modified[/bold green]",
                    border_style="green",
                    expand=False,
                )
            )

        elapsed = time.monotonic() - self._start_time
        self.console.print(
            Text(
                f"  Completed in {iterations} step(s) ({elapsed:.1f}s)",
                style="dim",
            )
        )

    def on_iteration_start(self, iteration: int, max_iterations: int) -> None:
        self.console.print(
            Text(f"  Step {iteration}/{max_iterations}", style="dim")
        )

    def on_llm_start(self) -> None:
        self._token_buffer = ""
        self._live = Live(
            Text(""),
            console=self.console,
            transient=True,
            refresh_per_second=12,
        )
        self._live.start()

    def on_token(self, token: str) -> None:
        self._token_buffer += token
        if self._live is not None:
            try:
                self._live.update(Markdown(self._token_buffer))
            except Exception:
                self._live.update(Text(self._token_buffer))

    def on_llm_end(self, content: str) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None
        if content.strip():
            self.console.print(Markdown(content))

    def on_tool_start(self, tool_call: ToolCall) -> None:
        icon, color = _TOOL_STYLES.get(
            tool_call.function.name, _DEFAULT_TOOL_STYLE
        )
        args_preview = ", ".join(
            f"{k}={v}" for k, v in tool_call.function.arguments.items()
        )
        self.console.print(
            Text(f"  {icon} {tool_call.function.name}({args_preview})", style=color)
        )

    def on_tool_end(self, tool_call: ToolCall, result: ToolResult) -> None:
        preview = result.content[:120]
        if len(result.content) > 120:
            preview += "..."
        self.console.print(Text(f"    {preview}", style="dim"))

    def on_error(self, error: Exception) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None
        self.console.print(f"  [bold red]Error:[/bold red] {error}")
