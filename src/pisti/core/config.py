"""Configuration loading."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    timeout: float = 120.0


class AgentConfig(BaseModel):
    model: str = "qwen2.5-coder:7b"
    max_iterations: int = 20
    context_window: int = 8192


class AgentsConfig(BaseModel):
    coder: AgentConfig = Field(default_factory=AgentConfig)


class ToolsConfig(BaseModel):
    max_read_chars: int = 50_000


class PistiConfig(BaseModel):
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)


_SEARCH_PATHS = [
    Path(".pisti/config.yaml"),
    Path.home() / ".config/pisti/config.yaml",
]


def load_config(path: Path | None = None) -> PistiConfig:
    """Load config from file or return defaults."""
    if path and path.exists():
        return PistiConfig.model_validate(yaml.safe_load(path.read_text()) or {})

    for candidate in _SEARCH_PATHS:
        if candidate.exists():
            return PistiConfig.model_validate(
                yaml.safe_load(candidate.read_text()) or {}
            )

    return PistiConfig()
