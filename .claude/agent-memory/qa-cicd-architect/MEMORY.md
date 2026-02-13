# QA & CI/CD Architect Memory

## Project: Pisti CLI

### Testing Patterns That Work

#### 1. Streaming LLM Testing
- Use mock LLM that yields chunks asynchronously to simulate real streaming
- Capture events through RecordingEventHandler for verification
- Test both content streaming and tool call handling
```python
async def chat_stream(self, messages, tools=None):
    for word in content.split():
        yield LLMResponse(message=Message(content=word), done=False)
    yield LLMResponse(message=Message(tool_calls=...), done=True)
```

#### 2. Rich Console Output Testing
- Create Console with StringIO buffer for output capture
- Use `force_terminal=True` to enable ANSI codes in tests
- Filter ANSI escape sequences to verify actual content
- Check for word patterns (4+ letters) rather than trying to clean all control codes
- Verify Live display state directly (`handler._live is None`)

#### 3. REPL/Interactive Testing
- Mock `Prompt.ask` with `side_effect` for multi-turn input
- Track agent call patterns to verify session continuity
- Check `continue_session` flag progression (False → True)
- Test edge cases: empty input, EOF, Ctrl+C, exceptions

#### 4. CLI Testing with Typer
- Use `typer.testing.CliRunner` for command invocation
- Mock internal components (`_build_coder_agent`) not external imports
- Patch at the import location (e.g., `pisti.cli.repl.run_interactive_session`)
- Use AsyncMock for async methods, MagicMock for sync

### Edge Cases That Matter

1. **Empty Content**: LLM returns tool calls with no text - causes ANSI codes but no visible output
2. **AsyncMock Warnings**: Using AsyncMock for Rich Console causes "never awaited" warnings - expected and safe
3. **Panel/Rich Objects**: Check `isinstance(call[0][0], Panel)` rather than comparing objects directly
4. **Escape Sequences**: Look for letter-only sequences to find real words, not mixed alphanumeric (ANSI codes)

### Test Organization

```
tests/
  cli/          - Unit tests for CLI components
  integration/  - E2E tests with full workflows
  agents/       - Agent behavior tests
  tools/        - Tool execution tests
```

### Quality Metrics Achieved

- 98 tests total (46 original + 52 new)
- 100% pass rate
- ~0.4s execution time for full suite
- Comprehensive E2E coverage of streaming, REPL, and tool visualization

### Common Pitfalls Avoided

1. **Don't** try to fully clean ANSI codes - look for content patterns instead
2. **Don't** use `pytest.approx` for object matching - use isinstance
3. **Don't** mock at import time - mock where the function is used
4. **Do** test session continuity with explicit flag checks
5. **Do** verify cleanup (provider.close()) in both success and error paths

### Tools Used

- pytest with asyncio plugin
- typer.testing.CliRunner for CLI testing
- unittest.mock for controlled behavior
- Rich Console with StringIO for output capture
- respx for HTTP mocking (if needed for LLM providers)

### Future Testing Recommendations

1. Integration tests with real Ollama instance (mark as slow/integration)
2. Visual regression tests for terminal output
3. Performance benchmarks for streaming latency
4. Memory leak tests for long REPL sessions
5. Cross-platform terminal compatibility tests
