"""Ollama LLM provider."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from pisti.core.errors import LLMConnectionError, LLMError
from pisti.core.types import FunctionCall, LLMResponse, Message, ToolCall

from .base import LLMProvider


def _message_to_wire(msg: Message) -> dict[str, Any]:
    """Convert internal Message to Ollama wire format."""
    wire: dict[str, Any] = {"role": msg.role, "content": msg.content}
    if msg.tool_calls:
        wire["tool_calls"] = [
            {
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
            }
            for tc in msg.tool_calls
        ]
    return wire


def _wire_to_message(data: dict[str, Any]) -> Message:
    """Convert Ollama response message to internal Message."""
    msg_data = data.get("message", {})
    tool_calls: list[ToolCall] = []
    for tc in msg_data.get("tool_calls", []):
        fn = tc.get("function", {})
        tool_calls.append(
            ToolCall(
                id=str(uuid.uuid4()),
                function=FunctionCall(
                    name=fn.get("name", ""),
                    arguments=fn.get("arguments", {}),
                ),
            )
        )
    return Message(
        role=msg_data.get("role", "assistant"),
        content=msg_data.get("content", ""),
        tool_calls=tool_calls,
    )


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:7b",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(timeout=timeout)

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, object]] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [_message_to_wire(m) for m in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = await self._client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as e:
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is Ollama running? Try: ollama serve"
            ) from e
        except httpx.HTTPStatusError as e:
            raise LLMError(f"Ollama returned {e.response.status_code}") from e

        data = resp.json()
        return LLMResponse(
            message=_wire_to_message(data),
            model=data.get("model", self.model),
            done=data.get("done", True),
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict[str, object]] | None = None,
    ) -> AsyncIterator[LLMResponse]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [_message_to_wire(m) for m in messages],
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        try:
            async with self._client.stream(
                "POST", f"{self.base_url}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    import json

                    data = json.loads(line)
                    yield LLMResponse(
                        message=_wire_to_message(data),
                        model=data.get("model", self.model),
                        done=data.get("done", False),
                    )
        except httpx.ConnectError as e:
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self.base_url}."
            ) from e

    async def close(self) -> None:
        await self._client.aclose()
