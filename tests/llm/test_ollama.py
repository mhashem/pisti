"""Tests for Ollama provider."""

import httpx
import pytest
import respx

from pisti.core.errors import LLMConnectionError, LLMError
from pisti.core.types import Message
from pisti.llm.ollama import OllamaProvider


@pytest.fixture
def provider():
    return OllamaProvider(base_url="http://localhost:11434", model="test-model")


@pytest.mark.asyncio
async def test_chat_simple_response(provider: OllamaProvider):
    with respx.mock:
        respx.post("http://localhost:11434/api/chat").mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "test-model",
                    "message": {"role": "assistant", "content": "Hello!"},
                    "done": True,
                },
            )
        )

        messages = [Message(role="user", content="Hi")]
        response = await provider.chat(messages)

        assert response.message.content == "Hello!"
        assert response.message.role == "assistant"
        assert response.done is True
        assert response.is_final_answer is True

    await provider.close()


@pytest.mark.asyncio
async def test_chat_with_tool_calls(provider: OllamaProvider):
    with respx.mock:
        respx.post("http://localhost:11434/api/chat").mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "test-model",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "read_file",
                                    "arguments": {"path": "main.py"},
                                }
                            }
                        ],
                    },
                    "done": True,
                },
            )
        )

        messages = [Message(role="user", content="Read main.py")]
        response = await provider.chat(messages)

        assert len(response.message.tool_calls) == 1
        tc = response.message.tool_calls[0]
        assert tc.function.name == "read_file"
        assert tc.function.arguments == {"path": "main.py"}
        assert tc.id  # UUID was generated
        assert response.is_final_answer is False

    await provider.close()


@pytest.mark.asyncio
async def test_chat_connection_error(provider: OllamaProvider):
    with respx.mock:
        respx.post("http://localhost:11434/api/chat").mock(
            side_effect=httpx.ConnectError("refused")
        )

        with pytest.raises(LLMConnectionError, match="Cannot connect"):
            await provider.chat([Message(role="user", content="Hi")])

    await provider.close()


@pytest.mark.asyncio
async def test_chat_http_error(provider: OllamaProvider):
    with respx.mock:
        respx.post("http://localhost:11434/api/chat").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        with pytest.raises(LLMError, match="500"):
            await provider.chat([Message(role="user", content="Hi")])

    await provider.close()
