"""Tests for memory.store.MemoryStore."""

import pytest

from memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    """Create a MemoryStore backed by a temporary directory."""
    return MemoryStore(tmp_path)


class TestReadFile:
    def test_missing_file_returns_empty(self, store):
        assert store.read_file("MEMORY.md") == ""

    def test_read_full_file(self, store):
        store.write_memory("line1\nline2\nline3\n")
        content = store.read_file("MEMORY.md")
        assert content == "line1\nline2\nline3\n"

    def test_read_line_range(self, store):
        store.write_memory("line1\nline2\nline3\nline4\n")
        content = store.read_file("MEMORY.md", start_line=2, end_line=3)
        assert content == "line2\nline3\n"

    def test_start_line_beyond_file(self, store):
        store.write_memory("line1\n")
        content = store.read_file("MEMORY.md", start_line=100)
        assert content == ""

    def test_end_line_beyond_file(self, store):
        store.write_memory("line1\nline2\n")
        content = store.read_file("MEMORY.md", start_line=1, end_line=999)
        assert content == "line1\nline2\n"

    def test_read_log_file(self, store):
        log_dir = store.logs_dir
        log_dir.mkdir(parents=True)
        (log_dir / "2026-03-05.md").write_text("log entry\n", encoding="utf-8")
        content = store.read_file("memory_logs/2026-03-05.md")
        assert content == "log entry\n"


class TestWriteMemory:
    def test_create_new(self, store):
        store.write_memory("hello world")
        assert store.memory_path.read_text(encoding="utf-8") == "hello world"

    def test_overwrite_existing(self, store):
        store.write_memory("old")
        store.write_memory("new")
        assert store.memory_path.read_text(encoding="utf-8") == "new"

    def test_creates_base_dir(self, tmp_path):
        nested = tmp_path / "deep" / "nested"
        s = MemoryStore(nested)
        s.write_memory("content")
        assert s.memory_path.read_text(encoding="utf-8") == "content"


class TestAppendToDailyLog:
    def test_creates_dir_and_file(self, store):
        path = store.append_to_daily_log("test entry", date="2026-03-05")
        assert path == "memory_logs/2026-03-05.md"
        content = (store.logs_dir / "2026-03-05.md").read_text(encoding="utf-8")
        assert "test entry" in content

    def test_appends_with_timestamp(self, store):
        store.append_to_daily_log("first", date="2026-03-05")
        store.append_to_daily_log("second", date="2026-03-05")
        content = (store.logs_dir / "2026-03-05.md").read_text(encoding="utf-8")
        assert "first" in content
        assert "second" in content
        # Timestamp format [HH:MM:SS]
        assert content.count("[") >= 2

    def test_default_date_is_today(self, store):
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        path = store.append_to_daily_log("auto date")
        assert today in path


class TestSearch:
    def test_empty_keywords(self, store):
        assert store.search([]) == []

    def test_no_files_returns_empty(self, store):
        assert store.search(["anything"]) == []

    def test_single_keyword_match(self, store):
        store.write_memory("The agent got stuck on floor 1\nFloor 2 was never reached\n")
        results = store.search(["floor"])
        assert len(results) == 2
        assert all(r.score == 1.0 for r in results)

    def test_multiple_keyword_scoring(self, store):
        store.write_memory("arrow keys stuck floor\nclick worked\narrow keys failed\n")
        results = store.search(["arrow", "stuck"])
        # First line matches both keywords (score 2), third line matches one (score 1)
        assert results[0].score == 2.0
        assert "arrow keys stuck" in results[0].content

    def test_case_insensitive(self, store):
        store.write_memory("MEMORY is Important\n")
        results = store.search(["memory", "important"])
        assert len(results) == 1
        assert results[0].score == 2.0

    def test_max_results(self, store):
        store.write_memory("\n".join(f"line {i} match" for i in range(20)))
        results = store.search(["match"], max_results=5)
        assert len(results) == 5

    def test_searches_log_files(self, store):
        store.logs_dir.mkdir(parents=True)
        (store.logs_dir / "2026-03-05.md").write_text("found the key\n", encoding="utf-8")
        results = store.search(["key"])
        assert len(results) == 1
        assert results[0].file_path == "memory_logs/2026-03-05.md"

    def test_search_across_multiple_files(self, store):
        store.write_memory("agent stuck on floor 1\n")
        store.logs_dir.mkdir(parents=True)
        (store.logs_dir / "2026-03-05.md").write_text("stuck in loop\n", encoding="utf-8")
        results = store.search(["stuck"])
        assert len(results) == 2

    def test_result_has_line_number(self, store):
        store.write_memory("no match\nno match\ntarget line\n")
        results = store.search(["target"])
        assert results[0].line_number == 3

    def test_to_dict(self, store):
        store.write_memory("test content\n")
        results = store.search(["test"])
        d = results[0].to_dict()
        assert set(d.keys()) == {"file_path", "line_number", "content", "score"}


class TestListLogFiles:
    def test_no_logs_dir(self, store):
        assert store.list_log_files() == []

    def test_empty_logs_dir(self, store):
        store.logs_dir.mkdir(parents=True)
        assert store.list_log_files() == []

    def test_returns_sorted(self, store):
        store.logs_dir.mkdir(parents=True)
        (store.logs_dir / "2026-03-05.md").write_text("", encoding="utf-8")
        (store.logs_dir / "2026-03-01.md").write_text("", encoding="utf-8")
        (store.logs_dir / "2026-03-10.md").write_text("", encoding="utf-8")
        files = store.list_log_files()
        assert files == [
            "memory_logs/2026-03-01.md",
            "memory_logs/2026-03-05.md",
            "memory_logs/2026-03-10.md",
        ]
