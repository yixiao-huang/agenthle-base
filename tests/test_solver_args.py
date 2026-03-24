"""Tests for solver argument parsing."""

from pathlib import Path

from cua_bench.batch.solver import parse_args


class TestParseArgs:
    def test_parses_thinking_flags(self):
        args = parse_args(
            [
                "solver.py",
                "./tasks/game/mota_24_easy",
                "--thinking-level",
                "medium",
                "--flush-thinking-level",
                "off",
                "--compaction-thinking-level",
                "low",
                "--summary-model",
                "openai/gpt-4o-mini",
            ]
        )

        assert args["env_path"] == Path("./tasks/game/mota_24_easy")
        assert args["thinking_level"] == "medium"
        assert args["flush_thinking_level"] == "off"
        assert args["compaction_thinking_level"] == "low"
        assert args["summary_model"] == "openai/gpt-4o-mini"
