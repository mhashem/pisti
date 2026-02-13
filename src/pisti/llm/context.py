"""Context window management."""

from __future__ import annotations

from pisti.core.types import Message

CHARS_PER_TOKEN = 4


class ContextWindowManager:
    """Simple char-based context trimmer.

    Keeps the system message + the last `keep_last` messages,
    truncating if the total exceeds the token budget.
    """

    def __init__(self, max_tokens: int = 8192, keep_last: int = 6) -> None:
        self.max_chars = max_tokens * CHARS_PER_TOKEN
        self.keep_last = keep_last

    def trim(self, messages: list[Message]) -> list[Message]:
        """Return a trimmed copy of messages that fits in budget."""
        if not messages:
            return []

        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        # Keep last N non-system messages
        kept = non_system[-self.keep_last :] if non_system else []
        result = system_msgs + kept

        # Check total size and drop oldest non-system if over budget
        while (
            len(result) > len(system_msgs) + 1
            and self._char_count(result) > self.max_chars
        ):
            # Remove the oldest non-system message
            for i, m in enumerate(result):
                if m.role != "system":
                    result.pop(i)
                    break

        return result

    @staticmethod
    def _char_count(messages: list[Message]) -> int:
        return sum(len(m.content) for m in messages)
