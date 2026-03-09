"""
Memory tools for the agent - search, read, and write memory files.
"""

from typing import Union

from agent.tools.base import BaseTool, register_tool

from .store import MemoryStore

_WRITE_TARGETS = ("session", "memory", "task_memory")


@register_tool("memory_search")
class MemorySearchTool(BaseTool):
    """Tool for searching memory files by keywords.

    Reference: openclaw/src/agents/tools/memory-tool.ts (createMemorySearchTool).
    Intentional deviations from OpenClaw:
    - Accepts both `query` (string) and `keywords` (list[str]); OpenClaw uses only `query`.
      `query` is split on whitespace internally. `keywords` is a convenience shorthand.
    - No `minScore` parameter (planned for US-MEM-SQL when BM25 scores are continuous).
    - Returns plain text lines, not structured JSON (CUA agent consumes text).
    """

    def __init__(self, store: MemoryStore, cfg=None):
        self.store = store
        super().__init__(cfg)

    @property
    def description(self) -> str:
        return (
            "Search your memory files (MEMORY.md, TASK_MEMORY.md, session logs, "
            "and daily logs) by keywords. Use this to recall past observations, "
            "strategies, mistakes, or patterns before making decisions. "
            "Returns matched lines with file path and line number."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string (split on whitespace into keywords).",
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of keywords to search for. Lines matching more keywords rank higher.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 10).",
                },
            },
            "required": [],
        }

    def call(self, params: Union[str, dict], **kwargs) -> str:
        params_dict = self._verify_json_format_args(params)

        keywords = params_dict.get("keywords", [])
        query = params_dict.get("query", "")

        # Resolve keywords: prefer explicit keywords, fall back to splitting query
        if not keywords and query:
            keywords = query.strip().split()
        if not keywords:
            raise ValueError(
                "'keywords' or 'query' must be provided. "
                "Pass keywords: [...] or query: 'space separated terms'."
            )

        max_results = params_dict.get("max_results", 10)

        try:
            results = self.store.search(keywords, max_results=max_results)
        except Exception as e:
            return f"Error searching memory: {e}"

        if not results:
            return f"No memory results found for keywords: {keywords}"

        lines = []
        for r in results:
            lines.append(f"[{r.file_path}:{r.line_number}] (score {r.score}) {r.content}")
        return "\n".join(lines)


@register_tool("memory_get")
class MemoryGetTool(BaseTool):
    """Tool for reading memory files or specific line ranges.

    Reference: openclaw/src/agents/tools/memory-tool.ts (createMemoryGetTool)
    and openclaw/src/memory/manager.ts (readFile). API shape (path/from/lines),
    .md-only restriction, and path traversal checks follow that implementation.
    """

    def __init__(self, store: MemoryStore, cfg=None):
        self.store = store
        super().__init__(cfg)

    @property
    def description(self) -> str:
        return (
            "Safe snippet read from MEMORY.md or memory_logs/*.md with optional "
            "from/lines; use after memory_search to pull only the needed lines "
            "and keep context small."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the memory file (e.g. 'MEMORY.md' or 'memory_logs/2026-03-05.md').",
                },
                "from": {
                    "type": "integer",
                    "description": "1-based starting line number (default: 1).",
                },
                "lines": {
                    "type": "integer",
                    "description": "Number of lines to read from the starting line (default: entire file).",
                },
            },
            "required": ["path"],
        }

    def call(self, params: Union[str, dict], **kwargs) -> str:
        params_dict = self._verify_json_format_args(params)

        file_path = params_dict.get("path", "")

        # Security: reject path traversal and absolute paths
        if ".." in file_path or file_path.startswith("/"):
            return "Error: path traversal is not allowed. Use a relative path within memory."

        # Only allow .md files
        if not file_path.endswith(".md"):
            return "Error: only .md files can be read."

        start_line = params_dict.get("from", 1)
        num_lines = params_dict.get("lines", None)

        end_line = (start_line + num_lines - 1) if num_lines is not None else None

        content = self.store.read_file(file_path, start_line=start_line, end_line=end_line)

        if not content:
            return f"File '{file_path}' not found or empty."

        return content


@register_tool("memory_write")
class MemoryWriteTool(BaseTool):
    """Tool for writing content to memory files."""

    def __init__(self, store: MemoryStore, cfg=None):
        self.store = store
        super().__init__(cfg)

    @property
    def description(self) -> str:
        return (
            "Write content to one of three memory targets:\n"
            "- 'session' (default): append to the current session log (timestamped)\n"
            "- 'memory': overwrite MEMORY.md (long-term cross-session knowledge)\n"
            "- 'task_memory': overwrite TASK_MEMORY.md (task-specific knowledge)"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The text content to write.",
                },
                "target": {
                    "type": "string",
                    "enum": list(_WRITE_TARGETS),
                    "description": "Where to write: 'session' (default), 'memory', or 'task_memory'.",
                },
            },
            "required": ["content"],
        }

    def call(self, params: Union[str, dict], **kwargs) -> str:
        params_dict = self._verify_json_format_args(params)

        content = params_dict.get("content", "")
        if not content or not content.strip():
            return "Error: content must be a non-empty string (not blank/whitespace)."

        target = params_dict.get("target", "session")
        if target not in _WRITE_TARGETS:
            return f"Error: target must be one of {_WRITE_TARGETS}, got '{target}'."

        if target == "session":
            try:
                path = self.store.append_to_session_log(content)
            except RuntimeError:
                return (
                    "Error: no session initialized. "
                    "The session must be started (init_session) before writing to it."
                )
        elif target == "memory":
            self.store.write_memory(content)
            path = "MEMORY.md"
        else:  # task_memory
            self.store.write_task_memory(content)
            path = "TASK_MEMORY.md"

        return f"Wrote {len(content)} bytes to {path}"
