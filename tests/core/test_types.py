"""Tests for core types."""

from pisti.core.types import (
    AgentResult,
    AgentRole,
    FunctionCall,
    LLMResponse,
    Message,
    Priority,
    TaskState,
    ToolCall,
    ToolResult,
)


def test_agent_role_values():
    assert AgentRole.CODER == "coder"
    assert AgentRole.REVIEWER == "reviewer"


def test_task_state_values():
    assert TaskState.PENDING == "pending"
    assert TaskState.FAILED == "failed"


def test_priority_values():
    assert Priority.HIGH == "high"


def test_message_defaults():
    msg = Message(role="user", content="hello")
    assert msg.tool_calls == []
    assert msg.tool_call_id is None


def test_tool_call_structure():
    tc = ToolCall(
        id="abc", function=FunctionCall(name="read_file", arguments={"path": "foo.py"})
    )
    assert tc.function.name == "read_file"
    assert tc.function.arguments == {"path": "foo.py"}


def test_llm_response_is_final_answer():
    # Final answer: done + content + no tool calls
    resp = LLMResponse(message=Message(role="assistant", content="Done!"))
    assert resp.is_final_answer is True

    # Not final: has tool calls
    resp2 = LLMResponse(
        message=Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="1", function=FunctionCall(name="read_file"))],
        )
    )
    assert resp2.is_final_answer is False

    # Is final: no content but done and no tool calls
    resp3 = LLMResponse(message=Message(role="assistant", content=""))
    assert resp3.is_final_answer is True


def test_agent_result_defaults():
    result = AgentResult(summary="done")
    assert result.files_modified == []
    assert result.iterations == 0


def test_tool_result():
    tr = ToolResult(tool_call_id="abc", name="read_file", content="hello world")
    assert tr.content == "hello world"
