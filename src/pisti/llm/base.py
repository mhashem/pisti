"""LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pisti.core.types import LLMResponse, Message


class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, object]] | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict[str, object]] | None = None,
    ) -> AsyncIterator[LLMResponse]: ...

    @abstractmethod
    async def close(self) -> None: ...
