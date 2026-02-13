"""Agent event handler protocol and null implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pisti.core.types import ToolCall, ToolResult


@runtime_checkable
class AgentEventHandler(Protocol):
    """Protocol for receiving agent lifecycle events."""

    def on_agent_start(self, agent_name: str, instruction: str) -> None: ...
    def on_agent_end(
        self, summary: str, files_modified: list[str], iterations: int
    ) -> None: ...

    def on_iteration_start(self, iteration: int, max_iterations: int) -> None: ...

    def on_llm_start(self) -> None: ...
    def on_token(self, token: str) -> None: ...
    def on_llm_end(self, content: str) -> None: ...

    def on_tool_start(self, tool_call: ToolCall) -> None: ...
    def on_tool_end(self, tool_call: ToolCall, result: ToolResult) -> None: ...

    def on_error(self, error: Exception) -> None: ...


class NullEventHandler:
    """No-op event handler used as default."""

    def on_agent_start(self, agent_name: str, instruction: str) -> None:
        pass

    def on_agent_end(
        self, summary: str, files_modified: list[str], iterations: int
    ) -> None:
        pass

    def on_iteration_start(self, iteration: int, max_iterations: int) -> None:
        pass

    def on_llm_start(self) -> None:
        pass

    def on_token(self, token: str) -> None:
        pass

    def on_llm_end(self, content: str) -> None:
        pass

    def on_tool_start(self, tool_call: ToolCall) -> None:
        pass

    def on_tool_end(self, tool_call: ToolCall, result: ToolResult) -> None:
        pass

    def on_error(self, error: Exception) -> None:
        pass
