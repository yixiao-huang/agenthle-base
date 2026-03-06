"""
Memory search tool for the agent - enables keyword search across memory files.
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
