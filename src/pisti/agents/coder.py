"""Coder agent."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Template

from pisti.core.types import Message

from .base import BaseAgent

_PROMPT_PATH = Path(__file__).parent / "prompts" / "coder.md"


class CoderAgent(BaseAgent):
    @property
    def agent_name(self) -> str:
        return "Coder"

    def _build_initial_messages(self, instruction: str) -> list[Message]:
        template = Template(_PROMPT_PATH.read_text())
        system_prompt = template.render(
            working_dir=str(self.working_dir),
            tool_names=", ".join(self.tool_registry.names()),
        )
        return [
            Message(role="system", content=system_prompt),
            Message(role="user", content=instruction),
        ]
