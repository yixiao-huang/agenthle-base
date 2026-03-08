"""
Memory tools for the agent - search and read memory files.
"""

from typing import Union

from agent.tools.base import BaseTool, register_tool

from .store import MemoryStore


@register_tool("memory_search")
class MemorySearchTool(BaseTool):
    """Tool for searching memory files by keywords."""

    def __init__(self, store: MemoryStore, cfg=None):
        self.store = store
        super().__init__(cfg)

    @property
    def description(self) -> str:
        return (
            "Search your memory files (long-term MEMORY.md and daily logs) by keywords. "
            "Use this to recall past observations, strategies, mistakes, or patterns "
            "before making decisions. Returns matched lines with file path and line number."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
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
            "required": ["keywords"],
        }

    def call(self, params: Union[str, dict], **kwargs) -> str:
        params_dict = self._verify_json_format_args(params)

        keywords = params_dict.get("keywords", [])
        if not keywords:
            raise ValueError("'keywords' must be a non-empty list of strings")

        max_results = params_dict.get("max_results", 10)
        results = self.store.search(keywords, max_results=max_results)

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
