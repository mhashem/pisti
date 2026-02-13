"""Tests for RichEventHandler (CLI UI)."""

from io import StringIO

import pytest
from rich.console import Console

from pisti.cli.ui import RichEventHandler
from pisti.core.types import FunctionCall, ToolCall, ToolResult


class TestRichEventHandler:
    """Test suite for RichEventHandler output formatting."""

    @pytest.fixture
    def console(self):
        """Create a Console that writes to a StringIO buffer."""
        buffer = StringIO()
        return Console(
            file=buffer, force_terminal=True, width=120, legacy_windows=False
        )

    @pytest.fixture
    def handler(self, console):
        """Create a RichEventHandler with a test console."""
        return RichEventHandler(console=console)

    def get_output(self, console: Console) -> str:
        """Get the output written to the console buffer."""
        return console.file.getvalue()  # type: ignore

    def test_agent_start_output(self, handler, console):
        """Test agent start formatting."""
        handler.on_agent_start("TestAgent", "Create hello.py")

        output = self.get_output(console)
        assert "TestAgent" in output
        # Should contain the bullet point character
        assert "●" in output or "•" in output

    def test_agent_end_with_files(self, handler, console):
        """Test agent end with files modified."""
        handler.on_agent_start("TestAgent", "test")
        handler.on_agent_end(
            summary="All done",
            files_modified=["hello.py", "test.py"],
            iterations=3,
        )

        output = self.get_output(console)
        assert "hello.py" in output
        assert "test.py" in output
        assert "3 step(s)" in output
        assert "Files Modified" in output

    def test_agent_end_no_files(self, handler, console):
        """Test agent end without files modified."""
        handler.on_agent_start("TestAgent", "test")
        handler.on_agent_end(summary="All done", files_modified=[], iterations=1)

        output = self.get_output(console)
        assert "1 step(s)" in output
        # Should not show Files Modified panel
        assert "Files Modified" not in output

    def test_iteration_start(self, handler, console):
        """Test iteration start formatting."""
        handler.on_iteration_start(2, 20)

        output = self.get_output(console)
        assert "Step 2/20" in output

    def test_llm_streaming_output(self, handler, console):
        """Test LLM streaming with tokens."""
        handler.on_llm_start()
        handler.on_token("Hello ")
        handler.on_token("world")
        handler.on_token("!")
        handler.on_llm_end("Hello world!")

        output = self.get_output(console)
        assert "Hello world!" in output

    def test_llm_empty_content(self, handler, console):
        """Test LLM with empty content (tool calls only)."""
        handler.on_llm_start()
        handler.on_llm_end("")

        output = self.get_output(console)
        # Empty content should not produce visible text output
        # The Live display creates control sequences but no visible text
        # Key behavior: Live should be stopped and no markdown content printed
        assert handler._live is None  # Live should be stopped

        # Check that there's no actual visible text (words/sentences)
        # by looking for sequences of letters only (not mixed with numbers/symbols)
        # ANSI codes may have "25h" etc, but actual words would be all letters
        import re
        # Find sequences of 4+ letters (actual words)
        words = re.findall(r'[a-zA-Z]{4,}', output)
        assert len(words) == 0  # No actual text content

    def test_tool_call_known_tool(self, handler, console):
        """Test tool call formatting for known tools."""
        tool_call = ToolCall(
            id="t1",
            function=FunctionCall(
                name="read_file",
                arguments={"path": "test.py"},
            ),
        )
        handler.on_tool_start(tool_call)

        output = self.get_output(console)
        assert "read_file" in output
        assert "path=test.py" in output
        # Should contain an icon (emoji)
        # Check for book emoji or similar
        assert any(char in output for char in ["📖", "📁", "✏", "🔍", "⚙"])

    def test_tool_call_unknown_tool(self, handler, console):
        """Test tool call formatting for unknown tools (default style)."""
        tool_call = ToolCall(
            id="t1",
            function=FunctionCall(
                name="custom_tool",
                arguments={"arg": "value"},
            ),
        )
        handler.on_tool_start(tool_call)

        output = self.get_output(console)
        assert "custom_tool" in output
        assert "arg=value" in output

    def test_tool_result_short(self, handler, console):
        """Test tool result with short content."""
        tool_call = ToolCall(
            id="t1",
            function=FunctionCall(name="echo", arguments={}),
        )
        result = ToolResult(
            tool_call_id="t1",
            name="echo",
            content="Short result",
        )
        handler.on_tool_end(tool_call, result)

        output = self.get_output(console)
        assert "Short result" in output

    def test_tool_result_long_truncated(self, handler, console):
        """Test tool result with long content gets truncated."""
        tool_call = ToolCall(
            id="t1",
            function=FunctionCall(name="read_file", arguments={}),
        )
        long_content = "x" * 200
        result = ToolResult(
            tool_call_id="t1",
            name="read_file",
            content=long_content,
        )
        handler.on_tool_end(tool_call, result)

        output = self.get_output(console)
        # Should be truncated at 120 chars + "..."
        assert "xxx" in output
        assert "..." in output
        assert len(output) < len(long_content)

    def test_error_handling(self, handler, console):
        """Test error formatting."""
        error = ValueError("Something went wrong")
        handler.on_error(error)

        output = self.get_output(console)
        assert "Error" in output
        assert "Something went wrong" in output

    def test_error_stops_live_display(self, handler, console):
        """Test that error stops any active live display."""
        handler.on_llm_start()
        handler.on_token("Starting...")
        handler.on_error(ValueError("Interrupted"))

        output = self.get_output(console)
        assert "Error" in output
        assert handler._live is None

    def test_full_workflow_sequence(self, handler, console):
        """Test a complete workflow with all events."""
        # Agent starts
        handler.on_agent_start("CoderAgent", "Create hello.py")

        # Iteration 1
        handler.on_iteration_start(1, 20)

        # LLM streams response
        handler.on_llm_start()
        handler.on_token("I'll create")
        handler.on_token(" the file")
        handler.on_llm_end("I'll create the file")

        # Tool call
        tool_call = ToolCall(
            id="t1",
            function=FunctionCall(
                name="write_file",
                arguments={"path": "hello.py", "content": "print('hello')"},
            ),
        )
        handler.on_tool_start(tool_call)

        result = ToolResult(
            tool_call_id="t1",
            name="write_file",
            content="File written successfully",
        )
        handler.on_tool_end(tool_call, result)

        # Iteration 2
        handler.on_iteration_start(2, 20)
        handler.on_llm_start()
        handler.on_token("Done!")
        handler.on_llm_end("Done!")

        # Agent ends
        handler.on_agent_end("Created hello.py", ["hello.py"], 2)

        output = self.get_output(console)

        # Verify key elements are present
        assert "CoderAgent" in output
        assert "Step 1/20" in output
        assert "Step 2/20" in output
        assert "write_file" in output
        assert "hello.py" in output
        assert "2 step(s)" in output
        assert "Files Modified" in output

    def test_multiple_tool_calls_same_iteration(self, handler, console):
        """Test multiple tool calls in the same iteration."""
        handler.on_iteration_start(1, 20)

        # First tool
        tool1 = ToolCall(
            id="t1",
            function=FunctionCall(name="read_file", arguments={"path": "a.py"}),
        )
        handler.on_tool_start(tool1)
        handler.on_tool_end(
            tool1,
            ToolResult(tool_call_id="t1", name="read_file", content="File content A"),
        )

        # Second tool
        tool2 = ToolCall(
            id="t2",
            function=FunctionCall(name="write_file", arguments={"path": "b.py"}),
        )
        handler.on_tool_start(tool2)
        handler.on_tool_end(
            tool2,
            ToolResult(tool_call_id="t2", name="write_file", content="Written B"),
        )

        output = self.get_output(console)
        assert "read_file" in output
        assert "write_file" in output
        assert "a.py" in output
        assert "b.py" in output

    def test_markdown_rendering(self, handler, console):
        """Test that markdown content is rendered properly."""
        handler.on_llm_start()
        markdown_content = "# Header\n\n**Bold text** and `code`"
        handler.on_token(markdown_content)
        handler.on_llm_end(markdown_content)

        output = self.get_output(console)
        # The markdown should be rendered, so check for presence
        # Exact rendering depends on Rich, but content should be there
        assert "Header" in output
        assert "Bold text" in output or "Bold" in output
        assert "code" in output

    def test_invalid_markdown_fallback(self, handler, console):
        """Test that invalid markdown falls back to plain text."""
        handler.on_llm_start()
        # Malformed markdown that might cause parsing issues
        invalid_md = "[[[broken]"
        handler.on_token(invalid_md)
        handler.on_llm_end(invalid_md)

        output = self.get_output(console)
        # Should still display the content even if markdown fails
        assert "broken" in output or "[[[" in output
