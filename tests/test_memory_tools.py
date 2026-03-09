"""Tests for memory tools (MemorySearchTool, MemoryGetTool, MemoryWriteTool)."""

import pytest

from memory.store import MemoryStore
from memory.tools import MemoryGetTool, MemorySearchTool, MemoryWriteTool


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
        assert params["required"] == []
        assert "query" in params["properties"]

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
        with pytest.raises(ValueError, match="keywords.*query"):
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

    def test_query_string_splits_to_keywords(self, store, tool):
        store.write_memory("arrow keys stuck floor\nclick worked\n")
        result = tool.call({"query": "arrow stuck"})
        assert "arrow keys stuck floor" in result

    def test_query_single_word(self, store, tool):
        store.write_memory("important observation here\n")
        result = tool.call({"query": "important"})
        assert "important" in result

    def test_keywords_takes_precedence_over_query(self, store, tool):
        store.write_memory("alpha line\nbeta line\n")
        # keywords provided — query should be ignored
        result = tool.call({"keywords": ["alpha"], "query": "beta"})
        assert "alpha" in result

    def test_empty_query_and_no_keywords_raises(self, tool):
        with pytest.raises(ValueError, match="keywords.*query"):
            tool.call({"query": ""})

    def test_no_query_no_keywords_raises(self, tool):
        with pytest.raises(ValueError, match="keywords.*query"):
            tool.call({})

    def test_store_error_returns_friendly_message(self, store, tool, monkeypatch):
        monkeypatch.setattr(store, "search", lambda *a, **kw: (_ for _ in ()).throw(IOError("disk error")))
        result = tool.call({"keywords": ["test"]})
        assert "Error searching memory" in result
        assert "disk error" in result


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


@pytest.fixture
def task_store(tmp_path):
    return MemoryStore(tmp_path, task_id="test_task")


@pytest.fixture
def write_tool(task_store):
    return MemoryWriteTool(task_store)


class TestMemoryWriteTool:
    def test_name_registered(self, write_tool):
        assert write_tool.name == "memory_write"

    def test_parameters_schema(self, write_tool):
        params = write_tool.parameters
        assert params["type"] == "object"
        assert "content" in params["properties"]
        assert "target" in params["properties"]
        assert params["required"] == ["content"]

    def test_write_session(self, task_store, write_tool):
        task_store.init_session()
        result = write_tool.call({"content": "session observation", "target": "session"})
        assert "Wrote" in result
        assert "bytes" in result
        # Verify file content
        session_files = list(task_store.task_dir.glob("session-*.md"))
        assert len(session_files) == 1
        assert "session observation" in session_files[0].read_text(encoding="utf-8")

    def test_write_memory(self, task_store, write_tool):
        result = write_tool.call({"content": "long-term insight", "target": "memory"})
        assert "Wrote" in result
        assert "MEMORY.md" in result
        assert task_store.memory_path.read_text(encoding="utf-8") == "long-term insight"

    def test_write_task_memory(self, task_store, write_tool):
        result = write_tool.call({"content": "task-specific note", "target": "task_memory"})
        assert "Wrote" in result
        assert "TASK_MEMORY.md" in result
        assert "task-specific note" in (task_store.task_dir / "TASK_MEMORY.md").read_text(encoding="utf-8")

    def test_empty_content_rejected(self, write_tool):
        result = write_tool.call({"content": ""})
        assert "Error" in result

    def test_whitespace_content_rejected(self, write_tool):
        result = write_tool.call({"content": "   \n\t  "})
        assert "Error" in result

    def test_default_target_is_session(self, task_store, write_tool):
        task_store.init_session()
        result = write_tool.call({"content": "default target test"})
        assert "Wrote" in result
        session_files = list(task_store.task_dir.glob("session-*.md"))
        assert any("default target test" in f.read_text(encoding="utf-8") for f in session_files)

    def test_no_session_init_error(self, task_store, write_tool):
        result = write_tool.call({"content": "should fail", "target": "session"})
        assert "Error" in result
        assert "session" in result.lower()

    def test_invalid_target_rejected(self, write_tool):
        result = write_tool.call({"content": "hello", "target": "bogus"})
        assert "Error" in result
        assert "bogus" in result

    def test_json_string_params(self, task_store, write_tool):
        result = write_tool.call('{"content": "json test", "target": "memory"}')
        assert "Wrote" in result
        assert task_store.memory_path.read_text(encoding="utf-8") == "json test"
