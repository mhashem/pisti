"""Error hierarchy."""


class PistiError(Exception):
    """Base error for all Pisti exceptions."""


class MaxIterationsError(PistiError):
    """Agent exceeded its iteration budget."""


class LLMError(PistiError):
    """Base error for LLM-related failures."""


class LLMConnectionError(LLMError):
    """Cannot connect to the LLM provider."""


class ToolExecutionError(PistiError):
    """A tool failed during execution."""


class ConfigError(PistiError):
    """Configuration is invalid or missing."""
