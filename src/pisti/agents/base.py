"""Base agent with agentic loop."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pisti.agents.events import AgentEventHandler, NullEventHandler
from pisti.core.errors import MaxIterationsError
from pisti.core.types import AgentResult, LLMResponse, Message, ToolCall, ToolResult
from pisti.llm.base import LLMProvider
from pisti.llm.context import ContextWindowManager
from pisti.tools.base import ToolRegistry


class BaseAgent(ABC):
    def __init__(
        self,
        llm: LLMProvider,
        tool_registry: ToolRegistry,
        working_dir: Path | None = None,
        max_iterations: int = 20,
        context_window: int = 8192,
        verbose: bool = False,
        event_handler: AgentEventHandler | None = None,
    ) -> None:
        self.llm = llm
        self.tool_registry = tool_registry
        self.working_dir = working_dir or Path.cwd()
        self.max_iterations = max_iterations
        self.verbose = verbose
        self._context_mgr = ContextWindowManager(max_tokens=context_window)
        self.files_modified: list[str] = []
        self.event_handler: AgentEventHandler = event_handler or NullEventHandler()
        self._messages: list[Message] = []

    @property
    def agent_name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def _build_initial_messages(self, instruction: str) -> list[Message]: ...

    async def run(
        self, instruction: str, *, continue_session: bool = False
    ) -> AgentResult:
        if continue_session and self._messages:
            self._messages.append(Message(role="user", content=instruction))
        else:
            self._messages = self._build_initial_messages(instruction)
            self.files_modified = []

        self.event_handler.on_agent_start(self.agent_name, instruction)
        try:
            result = await self._run_agentic_loop(self._messages)
            self.event_handler.on_agent_end(
                result.summary, result.files_modified, result.iterations
            )
            return result
        except Exception as e:
            self.event_handler.on_error(e)
            raise

    async def _call_llm(
        self,
        messages: list[Message],
        tools: list[dict[str, object]] | None = None,
    ) -> LLMResponse:
        """Call LLM with streaming if the handler is not a NullEventHandler."""
        if isinstance(self.event_handler, NullEventHandler):
            return await self.llm.chat(messages, tools=tools)
        return await self._call_llm_stream(messages, tools)

    async def _call_llm_stream(
        self,
        messages: list[Message],
        tools: list[dict[str, object]] | None = None,
    ) -> LLMResponse:
        """Stream LLM response, emitting tokens via the event handler."""
        self.event_handler.on_llm_start()
        accumulated_content = ""
        accumulated_tool_calls: list[ToolCall] = []
        last_response: LLMResponse | None = None

        async for chunk in self.llm.chat_stream(messages, tools=tools):
            token = chunk.message.content
            if token:
                accumulated_content += token
                self.event_handler.on_token(token)

            if chunk.message.tool_calls:
                for tc in chunk.message.tool_calls:
                    # Check if we already have this tool call ID (some providers might resend)
                    if not any(a.id == tc.id for a in accumulated_tool_calls):
                        accumulated_tool_calls.append(tc)

            last_response = chunk

        if last_response is None:
            last_response = LLMResponse(
                message=Message(role="assistant", content="")
            )

        # Merge accumulated content and tool calls
        final_message = Message(
            role="assistant",
            content=accumulated_content,
            tool_calls=accumulated_tool_calls,
        )
        response = LLMResponse(
            message=final_message,
            model=last_response.model,
            done=last_response.done,
        )
        self.event_handler.on_llm_end(accumulated_content)
        return response

    async def _run_agentic_loop(self, messages: list[Message]) -> AgentResult:
        for iteration in range(1, self.max_iterations + 1):
            self.event_handler.on_iteration_start(iteration, self.max_iterations)

            trimmed = self._context_mgr.trim(messages)
            response = await self._call_llm(
                trimmed, tools=self.tool_registry.schemas() or None
            )

            messages.append(response.message)

            if response.is_final_answer:
                return AgentResult(
                    summary=response.message.content or "(no response)",
                    files_modified=list(set(self.files_modified)),
                    iterations=iteration,
                )

            for tc in response.message.tool_calls:
                self.event_handler.on_tool_start(tc)
                result = await self._execute_tool_call(
                    tc.id, tc.function.name, tc.function.arguments
                )
                self.event_handler.on_tool_end(tc, result)
                messages.append(
                    Message(
                        role="tool",
                        content=result.content,
                        tool_call_id=result.tool_call_id,
                    )
                )

        raise MaxIterationsError(f"Agent exceeded {self.max_iterations} iterations")

    async def _execute_tool_call(
        self, call_id: str, name: str, arguments: dict[str, object]
    ) -> ToolResult:
        tool = self.tool_registry.get(name)
        if tool is None:
            return ToolResult(
                tool_call_id=call_id,
                name=name,
                content=f"Error: unknown tool '{name}'",
            )

        output = await tool.execute(**arguments)
        if isinstance(output, str):
            content = output
            metadata = {}
        else:
            content = output.content
            metadata = output.metadata

        # Handle file modifications via metadata
        if "files_modified" in metadata:
            self.files_modified.extend(metadata["files_modified"])

        return ToolResult(
            tool_call_id=call_id,
            name=name,
            content=content,
            metadata=metadata,
        )
