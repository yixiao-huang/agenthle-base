"""Tests for memory tools (MemorySearchTool, MemoryGetTool)."""

import pytest

from memory.store import MemoryStore
from memory.tools import MemoryGetTool, MemorySearchTool


@pytest.fixture
def store(tmp_path):
    return MemoryStore(tmp_path)


@pytest.fixture
def tool(store):
    return MemorySearchTool(store)


class TestMemorySearchTool:
    def test_name_registered(self, tool):
        assert tool.name == "memory_search"

    def test_description_non_empty(self, tool):
        assert len(tool.description) > 0

    def test_parameters_schema(self, tool):
        params = tool.parameters
        assert params["type"] == "object"
        assert "keywords" in params["properties"]
        assert params["required"] == ["keywords"]

    def test_search_basic(self, store, tool):
        store.write_memory("The agent got stuck on floor 1\nFloor 2 was reached\n")
        result = tool.call({"keywords": ["floor"]})
        assert "floor" in result.lower()
        assert "MEMORY.md" in result

    def test_search_no_results(self, store, tool):
        store.write_memory("some content\n")
        result = tool.call({"keywords": ["nonexistent"]})
        assert "No memory results found" in result

    def test_search_multiple_keywords(self, store, tool):
        store.write_memory("arrow keys stuck floor\nclick worked\narrow keys failed\n")
        result = tool.call({"keywords": ["arrow", "stuck"]})
        # Line with both keywords should appear first (higher score)
        lines = result.strip().split("\n")
        assert "score 2.0" in lines[0]

    def test_search_max_results(self, store, tool):
        store.write_memory("\n".join(f"line {i} match" for i in range(20)))
        result = tool.call({"keywords": ["match"], "max_results": 3})
        lines = [line for line in result.strip().split("\n") if line]
        assert len(lines) == 3

    def test_search_json_string_params(self, store, tool):
        store.write_memory("test content here\n")
        result = tool.call('{"keywords": ["test"]}')
        assert "test content here" in result

    def test_search_missing_keywords_raises(self, tool):
        with pytest.raises(ValueError, match="keywords"):
            tool.call({"not_keywords": ["x"]})

    def test_search_empty_keywords_raises(self, tool):
        with pytest.raises(ValueError, match="non-empty"):
            tool.call({"keywords": []})

    def test_result_includes_line_number(self, store, tool):
        store.write_memory("no match\nno match\ntarget line\n")
        result = tool.call({"keywords": ["target"]})
        assert ":3]" in result

    def test_searches_log_files(self, store, tool):
        store.logs_dir.mkdir(parents=True)
        (store.logs_dir / "2026-03-05.md").write_text("found the key\n", encoding="utf-8")
        result = tool.call({"keywords": ["key"]})
        assert "memory_logs/2026-03-05.md" in result


@pytest.fixture
def get_tool(store):
    return MemoryGetTool(store)


class TestMemoryGetTool:
    def test_name_registered(self, get_tool):
        assert get_tool.name == "memory_get"

    def test_parameters_schema(self, get_tool):
        params = get_tool.parameters
        assert params["type"] == "object"
        assert "path" in params["properties"]
        assert "from" in params["properties"]
        assert "lines" in params["properties"]
        assert params["required"] == ["path"]

    def test_read_full_file(self, store, get_tool):
        store.write_memory("line one\nline two\nline three\n")
        result = get_tool.call({"path": "MEMORY.md"})
        assert "line one" in result
        assert "line three" in result

    def test_read_line_range(self, store, get_tool):
        store.write_memory("line one\nline two\nline three\nline four\n")
        result = get_tool.call({"path": "MEMORY.md", "from": 2, "lines": 2})
        assert "line two" in result
        assert "line three" in result
        assert "line one" not in result
        assert "line four" not in result

    def test_path_traversal_rejected(self, get_tool):
        result = get_tool.call({"path": "../etc/passwd"})
        assert "not allowed" in result

    def test_absolute_path_rejected(self, get_tool):
        result = get_tool.call({"path": "/etc/passwd"})
        assert "not allowed" in result

    def test_non_md_rejected(self, get_tool):
        result = get_tool.call({"path": "secrets.txt"})
        assert "only .md files" in result

    def test_missing_file(self, get_tool):
        result = get_tool.call({"path": "nonexistent.md"})
        assert "not found or empty" in result

    def test_read_log_file(self, store, get_tool):
        store.logs_dir.mkdir(parents=True)
        (store.logs_dir / "2026-03-05.md").write_text("log entry here\n", encoding="utf-8")
        result = get_tool.call({"path": "memory_logs/2026-03-05.md"})
        assert "log entry here" in result

    def test_json_string_params(self, store, get_tool):
        store.write_memory("test content\n")
        result = get_tool.call('{"path": "MEMORY.md"}')
        assert "test content" in result
