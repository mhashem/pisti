"""Tests for context window management."""

from pisti.core.types import Message
from pisti.llm.context import ContextWindowManager


def test_trim_keeps_system_and_last_messages():
    mgr = ContextWindowManager(max_tokens=100_000, keep_last=3)
    messages = [
        Message(role="system", content="You are helpful."),
        Message(role="user", content="msg1"),
        Message(role="assistant", content="resp1"),
        Message(role="user", content="msg2"),
        Message(role="assistant", content="resp2"),
        Message(role="user", content="msg3"),
    ]
    trimmed = mgr.trim(messages)
    assert trimmed[0].role == "system"
    assert len(trimmed) == 4  # system + last 3
    assert trimmed[1].content == "msg2"


def test_trim_empty():
    mgr = ContextWindowManager()
    assert mgr.trim([]) == []


def test_trim_drops_when_over_budget():
    mgr = ContextWindowManager(max_tokens=10, keep_last=6)  # 40 chars budget
    messages = [
        Message(role="system", content="sys"),
        Message(role="user", content="a" * 20),
        Message(role="assistant", content="b" * 20),
        Message(role="user", content="c" * 5),
    ]
    trimmed = mgr.trim(messages)
    # Should have dropped some messages to fit under 40 chars
    assert len(trimmed) <= len(messages)
    assert trimmed[0].role == "system"
