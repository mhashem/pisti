"""Core domain types."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentRole(StrEnum):
    CODER = "coder"
    REVIEWER = "reviewer"
    PLANNER = "planner"


class TaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FunctionCall(BaseModel):
    name: str
    arguments: dict[str, object] = Field(default_factory=dict)


class ToolCall(BaseModel):
    id: str
    function: FunctionCall


class Message(BaseModel):
    role: str  # system, user, assistant, tool
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None


class ToolResult(BaseModel):
    tool_call_id: str
    name: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    message: Message
    model: str = ""
    done: bool = True

    @property
    def is_final_answer(self) -> bool:
        """True when the LLM is done and produced no tool calls."""
        return self.done and not self.message.tool_calls


class AgentResult(BaseModel):
    summary: str
    files_modified: list[str] = Field(default_factory=list)
    iterations: int = 0
