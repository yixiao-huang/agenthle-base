"""Tests for solver argument parsing."""

from pathlib import Path
from unittest.mock import MagicMock

from cua_bench.batch.solver import initialize_agent, parse_args


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
                "--vision-thinking-level",
                "minimal",
                "--summary-model",
                "openai/gpt-4o-mini",
            ]
        )

        assert args["env_path"] == Path("./tasks/game/mota_24_easy")
        assert args["thinking_level"] == "medium"
        assert args["flush_thinking_level"] == "off"
        assert args["compaction_thinking_level"] == "low"
        assert args["vision_thinking_level"] == "minimal"
        assert args["summary_model"] == "openai/gpt-4o-mini"

    def test_initialize_agent_forwards_aux_thinking_levels(self):
        agent_class = MagicMock()
        initialize_agent(
            {
                "model": "openai/gpt-5.4",
                "max_steps": 50,
                "summary_model": "openai/gpt-4o-mini",
                "thinking_level": "medium",
                "flush_thinking_level": "high",
                "compaction_thinking_level": "low",
                "vision_thinking_level": "off",
            },
            agent_class,
        )

        agent_class.assert_called_once_with(
            model="openai/gpt-5.4",
            max_steps=50,
            summary_model="openai/gpt-4o-mini",
            thinking_level="medium",
            flush_thinking_level="high",
            compaction_thinking_level="low",
            vision_thinking_level="off",
        )
