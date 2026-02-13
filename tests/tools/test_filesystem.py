"""Tests for filesystem tools."""

import pytest

from pisti.tools.filesystem import (
    ListDirectoryTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)


@pytest.fixture
def base_dir(tmp_path):
    return tmp_path


@pytest.mark.asyncio
async def test_write_and_read(base_dir):
    writer = WriteFileTool(base_dir=base_dir)
    reader = ReadFileTool(base_dir=base_dir)

    result = await writer.execute(path="hello.txt", content="Hello, world!")
    assert "Successfully wrote" in result

    content = await reader.execute(path="hello.txt")
    assert content == "Hello, world!"


@pytest.mark.asyncio
async def test_write_creates_parents(base_dir):
    writer = WriteFileTool(base_dir=base_dir)
    result = await writer.execute(path="sub/dir/file.py", content="print('hi')")
    assert "Successfully wrote" in result
    assert (base_dir / "sub" / "dir" / "file.py").exists()


@pytest.mark.asyncio
async def test_read_nonexistent(base_dir):
    reader = ReadFileTool(base_dir=base_dir)
    result = await reader.execute(path="missing.txt")
    assert "Error" in result


@pytest.mark.asyncio
async def test_read_truncation(base_dir):
    reader = ReadFileTool(base_dir=base_dir)
    (base_dir / "big.txt").write_text("x" * 60_000)
    result = await reader.execute(path="big.txt")
    assert "truncated" in result


@pytest.mark.asyncio
async def test_list_directory(base_dir):
    (base_dir / "a.py").touch()
    (base_dir / "b.py").touch()
    (base_dir / "subdir").mkdir()

    lister = ListDirectoryTool(base_dir=base_dir)
    result = await lister.execute(path=".")
    assert "a.py" in result
    assert "b.py" in result
    assert "subdir/" in result


@pytest.mark.asyncio
async def test_search_files(base_dir):
    (base_dir / "foo.py").touch()
    (base_dir / "bar.py").touch()
    (base_dir / "readme.md").touch()

    searcher = SearchFilesTool(base_dir=base_dir)
    result = await searcher.execute(pattern="*.py")
    assert "foo.py" in result
    assert "bar.py" in result
    assert "readme.md" not in result


@pytest.mark.asyncio
async def test_path_traversal_blocked(base_dir):
    reader = ReadFileTool(base_dir=base_dir)
    result = await reader.execute(path="../../etc/passwd")
    assert "Error" in result


@pytest.mark.asyncio
async def test_tool_schema():
    tool = ReadFileTool()
    schema = tool.schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "read_file"
    assert "parameters" in schema["function"]
