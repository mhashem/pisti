"""Filesystem tools for agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseTool

MAX_READ_CHARS = 50_000


class _FsTool(BaseTool):
    """Base for filesystem tools with path traversal protection."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or Path.cwd()).resolve()

    def _safe_path(self, path: str) -> Path:
        resolved = (self.base_dir / path).resolve()
        if not str(resolved).startswith(str(self.base_dir)):
            raise ValueError(f"Path traversal blocked: {path}")
        return resolved


class ReadFileTool(_FsTool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file. Returns file content as a string."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path to read.",
                },
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs: Any) -> str:
        path_str = kwargs.get("path", "")
        try:
            resolved = self._safe_path(path_str)
            content = resolved.read_text()
            if len(content) > MAX_READ_CHARS:
                return (
                    content[:MAX_READ_CHARS]
                    + f"\n... (truncated at {MAX_READ_CHARS} chars)"
                )
            return content
        except Exception as e:
            return f"Error reading {path_str}: {e}"


class WriteFileTool(_FsTool):
    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file. Creates parent directories if needed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path to write.",
                },
                "content": {"type": "string", "description": "Content to write."},
            },
            "required": ["path", "content"],
        }

    async def execute(self, **kwargs: Any) -> str:
        path_str = kwargs.get("path", "")
        content = kwargs.get("content", "")
        try:
            resolved = self._safe_path(path_str)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(str(content))
            return f"Successfully wrote {len(str(content))} chars to {path_str}"
        except Exception as e:
            return f"Error writing {path_str}: {e}"


class ListDirectoryTool(_FsTool):
    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return "List files and directories at a given path."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative directory path. Defaults to '.'.",
                    "default": ".",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> str:
        path_str = kwargs.get("path", ".")
        try:
            resolved = self._safe_path(path_str)
            if not resolved.is_dir():
                return f"Error: {path_str} is not a directory"
            entries: list[str] = []
            for entry in sorted(resolved.iterdir()):
                rel = entry.relative_to(self.base_dir)
                suffix = "/" if entry.is_dir() else ""
                entries.append(f"{rel}{suffix}")
            return "\n".join(entries) if entries else "(empty directory)"
        except Exception as e:
            return f"Error listing {path_str}: {e}"


class SearchFilesTool(_FsTool):
    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return "Search for files matching a pattern. Returns matching file paths."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. '**/*.py').",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, **kwargs: Any) -> str:
        pattern = kwargs.get("pattern", "")
        try:
            matches = sorted(self.base_dir.glob(pattern))
            results = []
            for m in matches[:100]:  # cap results
                try:
                    results.append(str(m.relative_to(self.base_dir)))
                except ValueError:
                    pass
            return "\n".join(results) if results else f"No files matching '{pattern}'"
        except Exception as e:
            return f"Error searching for {pattern}: {e}"
