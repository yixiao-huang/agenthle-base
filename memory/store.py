"""
MemoryStore - Markdown file storage layer for AgentHLE memory system.
Manages MEMORY.md (curated long-term), memory_logs/YYYY-MM-DD.md (daily append-only logs),
and task-scoped storage: tasks/<task_id>/TASK_MEMORY.md + session-NNN.md files.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class SearchResult:
    """A single search result from memory files."""

    def __init__(self, file_path: str, line_number: int, content: str, score: float):
        self.file_path = file_path
        self.line_number = line_number
        self.content = content
        self.score = score

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "content": self.content,
            "score": self.score,
        }


class MemoryStore:
    """
    Manages memory files: MEMORY.md, memory_logs/YYYY-MM-DD.md, and
    task-scoped storage (tasks/<task_id>/TASK_MEMORY.md + session-NNN.md).

    Args:
        base_dir: Root directory for memory files. MEMORY.md lives here,
                  memory_logs/ is a subdirectory.
        task_id: Optional task identifier for task-scoped storage.
    """

    MEMORY_FILE = "MEMORY.md"
    LOGS_DIR = "memory_logs"
    TASKS_DIR = "tasks"
    TASK_MEMORY_FILE = "TASK_MEMORY.md"

    def __init__(self, base_dir: str | Path, task_id: str | None = None):
        self.base_dir = Path(base_dir)
        self.task_id = task_id
        self._current_session_path: Path | None = None

    @property
    def memory_path(self) -> Path:
        return self.base_dir / self.MEMORY_FILE

    @property
    def logs_dir(self) -> Path:
        return self.base_dir / self.LOGS_DIR

    @property
    def task_dir(self) -> Path:
        """Path to the task-scoped directory. Raises ValueError if no task_id set."""
        if self.task_id is None:
            raise ValueError("task_dir requires a task_id to be set")
        return self.base_dir / self.TASKS_DIR / self.task_id

    def init_session(self) -> str:
        """
        Initialize a new session for the current task.

        Creates the task directory if absent, scans existing session-NNN.md files
        to determine the next session number, creates an empty session file, and
        stores the path for use by append_to_session_log().

        Returns:
            Relative path to the new session file (e.g. "tasks/mota_24_easy/session-001.md").
        """
        task_dir = self.task_dir  # raises if no task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        # Scan existing session files to determine next number
        existing = sorted(task_dir.glob("session-*.md"))
        next_num = 1
        if existing:
            # Extract the highest session number
            for f in existing:
                match = re.match(r"session-(\d+)\.md$", f.name)
                if match:
                    next_num = max(next_num, int(match.group(1)) + 1)

        session_file = task_dir / f"session-{next_num:03d}.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"# Session {next_num:03d} — {timestamp}\n\n"
        session_file.write_text(header, encoding="utf-8")
        self._current_session_path = session_file

        return str(session_file.relative_to(self.base_dir))

    def append_to_session_log(self, content: str) -> str:
        """
        Append timestamped content to the current session file.

        Args:
            content: Text to append.

        Returns:
            Relative path to the session file.

        Raises:
            RuntimeError: If init_session() has not been called.
        """
        if self._current_session_path is None:
            raise RuntimeError("init_session() must be called before append_to_session_log()")

        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"\n[{timestamp}] {content}\n"

        with open(self._current_session_path, "a", encoding="utf-8") as f:
            f.write(entry)

        return str(self._current_session_path.relative_to(self.base_dir))

    def write_task_memory(self, content: str) -> None:
        """Overwrite TASK_MEMORY.md for the current task. Creates dir if absent."""
        task_dir = self.task_dir  # raises if no task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / self.TASK_MEMORY_FILE).write_text(content, encoding="utf-8")

    def read_task_memory(self) -> str:
        """Read TASK_MEMORY.md content. Returns empty string if missing."""
        task_memory_path = self.task_dir / self.TASK_MEMORY_FILE
        if not task_memory_path.exists():
            return ""
        try:
            return task_memory_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    def list_session_files(self) -> list[str]:
        """Return sorted list of session-NNN.md relative paths for the current task."""
        task_dir = self.task_dir  # raises if no task_id
        if not task_dir.exists():
            return []
        files = sorted(task_dir.glob("session-*.md"))
        return [str(f.relative_to(self.base_dir)) for f in files]

    def read_file(
        self, relative_path: str, start_line: int = 1, end_line: Optional[int] = None
    ) -> str:
        """
        Read content from a memory file with optional line range.

        Args:
            relative_path: Path relative to base_dir (e.g. "MEMORY.md" or "memory_logs/2026-03-05.md")
            start_line: 1-based start line (default 1)
            end_line: 1-based end line inclusive (default: read to end)

        Returns:
            File content as string. Empty string if file doesn't exist.
        """
        file_path = self.base_dir / relative_path
        if not file_path.exists():
            return ""

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
        except (OSError, UnicodeDecodeError):
            return ""

        start_idx = max(0, start_line - 1)
        if end_line is not None:
            end_idx = min(len(lines), end_line)
        else:
            end_idx = len(lines)

        return "".join(lines[start_idx:end_idx])

    def append_to_daily_log(self, content: str, date: Optional[str] = None) -> str:
        """
        Append content to the daily log file.

        Args:
            content: Text to append
            date: Date string in YYYY-MM-DD format (default: today)

        Returns:
            Path to the log file (relative to base_dir)
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        self.logs_dir.mkdir(parents=True, exist_ok=True)

        log_file = self.logs_dir / f"{date}.md"
        relative_path = f"{self.LOGS_DIR}/{date}.md"

        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"\n[{timestamp}] {content}\n"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)

        return relative_path

    def write_memory(self, content: str) -> None:
        """Create or overwrite MEMORY.md."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.memory_path.write_text(content, encoding="utf-8")

    def search(self, keywords: List[str], max_results: int = 10) -> List[SearchResult]:
        """
        Case-insensitive substring search across all markdown files.

        Args:
            keywords: List of keywords to search for
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult sorted by score (descending)
        """
        if not keywords:
            return []

        keywords_lower = [k.lower() for k in keywords]
        results: list[SearchResult] = []

        md_files: list[Path] = []

        # When task_id is set, search task-scoped files first
        if self.task_id is not None:
            task_dir = self.task_dir
            if task_dir.exists():
                task_memory = task_dir / self.TASK_MEMORY_FILE
                if task_memory.exists():
                    md_files.append(task_memory)
                md_files.extend(sorted(task_dir.glob("session-*.md")))

        # Then global files
        if self.memory_path.exists():
            md_files.append(self.memory_path)
        if self.logs_dir.exists():
            md_files.extend(sorted(self.logs_dir.glob("*.md")))

        for file_path in md_files:
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue

            relative_path = str(file_path.relative_to(self.base_dir))

            for line_num, line in enumerate(lines, start=1):
                line_lower = line.lower()
                score = sum(1.0 for kw in keywords_lower if kw in line_lower)
                if score > 0:
                    results.append(
                        SearchResult(
                            file_path=relative_path,
                            line_number=line_num,
                            content=line.strip(),
                            score=score,
                        )
                    )

        results.sort(key=lambda r: (-r.score, r.file_path, r.line_number))
        return results[:max_results]

    def list_log_files(self) -> List[str]:
        """
        Return sorted list of existing daily log file paths (relative to base_dir).
        """
        if not self.logs_dir.exists():
            return []

        files = sorted(self.logs_dir.glob("*.md"))
        return [str(f.relative_to(self.base_dir)) for f in files]
