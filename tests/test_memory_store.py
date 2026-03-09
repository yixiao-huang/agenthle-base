"""Tests for memory.store.MemoryStore."""

import pytest

from memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    """Create a MemoryStore backed by a temporary directory."""
    return MemoryStore(tmp_path)


@pytest.fixture
def task_store(tmp_path):
    """Create a task-scoped MemoryStore backed by a temporary directory."""
    return MemoryStore(tmp_path, task_id="mota_24_easy")


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


# --- Task-scoped storage tests ---


class TestTaskDir:
    def test_raises_without_task_id(self, store):
        with pytest.raises(ValueError, match="task_dir requires a task_id"):
            _ = store.task_dir

    def test_returns_correct_path(self, task_store):
        assert task_store.task_dir == task_store.base_dir / "tasks" / "mota_24_easy"


class TestInitSession:
    def test_creates_dir_and_first_session(self, task_store):
        path = task_store.init_session()
        assert path == "tasks/mota_24_easy/session-001.md"
        assert task_store.task_dir.exists()
        assert (task_store.task_dir / "session-001.md").exists()

    def test_increments_session_number(self, task_store):
        task_store.init_session()
        # Create a new store instance (simulating a new session)
        store2 = MemoryStore(task_store.base_dir, task_id="mota_24_easy")
        path = store2.init_session()
        assert path == "tasks/mota_24_easy/session-002.md"

    def test_multiple_calls_on_same_instance(self, task_store):
        p1 = task_store.init_session()
        p2 = task_store.init_session()
        assert p1 == "tasks/mota_24_easy/session-001.md"
        assert p2 == "tasks/mota_24_easy/session-002.md"

    def test_session_file_has_header(self, task_store):
        task_store.init_session()
        content = (task_store.task_dir / "session-001.md").read_text(encoding="utf-8")
        assert content.startswith("# Session 001")

    def test_non_session_md_files_ignored_for_numbering(self, task_store):
        """TASK_MEMORY.md and other .md files don't affect session numbering."""
        task_store.task_dir.mkdir(parents=True)
        (task_store.task_dir / "TASK_MEMORY.md").write_text("notes", encoding="utf-8")
        (task_store.task_dir / "scratch.md").write_text("tmp", encoding="utf-8")
        path = task_store.init_session()
        assert path == "tasks/mota_24_easy/session-001.md"

    def test_raises_without_task_id(self, store):
        with pytest.raises(ValueError):
            store.init_session()


class TestAppendToSessionLog:
    def test_appends_with_timestamp(self, task_store):
        task_store.init_session()
        path = task_store.append_to_session_log("found a key on floor 2")
        assert path == "tasks/mota_24_easy/session-001.md"
        content = (task_store.task_dir / "session-001.md").read_text(encoding="utf-8")
        assert "found a key on floor 2" in content
        # Timestamp format [HH:MM:SS]
        assert "[" in content

    def test_raises_without_init_session(self, task_store):
        with pytest.raises(RuntimeError, match="init_session"):
            task_store.append_to_session_log("should fail")

    def test_multiple_appends(self, task_store):
        task_store.init_session()
        task_store.append_to_session_log("first observation")
        task_store.append_to_session_log("second observation")
        content = (task_store.task_dir / "session-001.md").read_text(encoding="utf-8")
        assert "first observation" in content
        assert "second observation" in content
        assert content.count("[") >= 2


class TestWriteTaskMemory:
    def test_creates_file(self, task_store):
        task_store.write_task_memory("yellow door needs yellow key")
        content = (task_store.task_dir / "TASK_MEMORY.md").read_text(encoding="utf-8")
        assert content == "yellow door needs yellow key"

    def test_overwrites_existing(self, task_store):
        task_store.write_task_memory("old knowledge")
        task_store.write_task_memory("new knowledge")
        content = (task_store.task_dir / "TASK_MEMORY.md").read_text(encoding="utf-8")
        assert content == "new knowledge"

    def test_creates_dir_if_absent(self, task_store):
        assert not task_store.task_dir.exists()
        task_store.write_task_memory("content")
        assert task_store.task_dir.exists()


class TestReadTaskMemory:
    def test_reads_content(self, task_store):
        task_store.write_task_memory("floor 3 strategy")
        assert task_store.read_task_memory() == "floor 3 strategy"

    def test_returns_empty_if_missing(self, task_store):
        task_store.task_dir.mkdir(parents=True, exist_ok=True)
        assert task_store.read_task_memory() == ""

    def test_returns_empty_if_dir_missing(self, task_store):
        # task_dir doesn't exist yet — should still return ""
        # But task_dir property raises if no task_id, so we need task_store
        assert task_store.read_task_memory() == ""


class TestListSessionFiles:
    def test_empty_when_no_dir(self, task_store):
        assert task_store.list_session_files() == []

    def test_returns_sorted(self, task_store):
        task_store.task_dir.mkdir(parents=True)
        # Create out of order
        (task_store.task_dir / "session-003.md").write_text("", encoding="utf-8")
        (task_store.task_dir / "session-001.md").write_text("", encoding="utf-8")
        (task_store.task_dir / "session-002.md").write_text("", encoding="utf-8")
        files = task_store.list_session_files()
        assert files == [
            "tasks/mota_24_easy/session-001.md",
            "tasks/mota_24_easy/session-002.md",
            "tasks/mota_24_easy/session-003.md",
        ]

    def test_ignores_non_session_files(self, task_store):
        task_store.task_dir.mkdir(parents=True)
        (task_store.task_dir / "session-001.md").write_text("", encoding="utf-8")
        (task_store.task_dir / "TASK_MEMORY.md").write_text("", encoding="utf-8")
        files = task_store.list_session_files()
        assert files == ["tasks/mota_24_easy/session-001.md"]


class TestScopedSearch:
    def test_searches_task_files_and_global(self, task_store):
        # Set up task-scoped files
        task_store.write_task_memory("yellow key is on floor 2\n")
        task_store.init_session()
        task_store.append_to_session_log("found yellow key")
        # Set up global memory
        task_store.write_memory("general strategy notes about keys\n")
        results = task_store.search(["key"])
        assert len(results) >= 2
        # Task files should appear (TASK_MEMORY.md and session)
        file_paths = [r.file_path for r in results]
        assert any("TASK_MEMORY" in fp for fp in file_paths)
        assert any("MEMORY.md" in fp for fp in file_paths)

    def test_task_id_none_unchanged(self, store):
        """Existing behavior: no task_id means only global files searched."""
        store.write_memory("test content\n")
        results = store.search(["test"])
        assert len(results) == 1
        assert results[0].file_path == "MEMORY.md"

    def test_task_files_included_in_search(self, task_store):
        """Task-scoped files are included alongside global files in search."""
        task_store.write_task_memory("keyword match\n")
        task_store.write_memory("keyword match\n")
        results = task_store.search(["keyword"])
        assert len(results) == 2
        file_paths = {r.file_path for r in results}
        assert any("TASK_MEMORY" in fp for fp in file_paths)
        assert any("MEMORY.md" in fp for fp in file_paths)
