"""Integration test: simulate an OpenClaw agent run and capture the system prompt.

Mocks the CUA SDK (OpenClawComputerAgent, MilestoneTool, session) so no VM is needed.
The test captures the `instructions` string passed to OpenClawComputerAgent and prints
it, verifying that MemoryStore, PromptBuilder, and bootstrap injection are wired
correctly.

Note: After US-OC-028, perform_task() instantiates OpenClawComputerAgent directly
(not the base ComputerAgent), so we patch OpenClawComputerAgent in the openclaw package.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cua_bench.agents.openclaw import MemoryStore


def _make_mock_session():
    """Create a mock DesktopSession with a _computer tool stub."""
    session = AsyncMock()
    computer_tool = MagicMock()
    computer_tool.name = "computer"
    computer_tool.description = "Mouse and keyboard control on the remote desktop"
    session._computer = computer_tool
    session.interface = MagicMock()
    session.screenshot = AsyncMock(return_value=b"\x89PNG")
    return session


def _make_mock_milestone():
    """Return a mock MilestoneTool with name/description."""
    tool = MagicMock()
    tool.name = "save_milestone_screenshot"
    tool.description = "Save the current screen as a milestone screenshot"
    return tool


async def _empty_async_gen():
    """Async generator that yields nothing (simulates 0-step agent run)."""
    return
    yield  # noqa: unreachable — makes this a generator


@pytest.fixture
def setup(tmp_path):
    """Set up logging dir and memory base dir for tests."""
    output_dir = tmp_path / "mota_24_easy"
    logging_dir = output_dir / "task_0_agent_logs"
    logging_dir.mkdir(parents=True)
    mem_base = tmp_path / "openclaw_memory"
    return logging_dir, mem_base


def _run_agent(logging_dir, mem_base, task_description="Navigate to floor 3 and pick up the yellow key."):
    """Run the agent with mocks, return the captured instructions string."""
    captured = {}

    def fake_openclaw_computer_agent(**kwargs):
        captured["instructions"] = kwargs.get("instructions", "")
        agent_mock = MagicMock()
        agent_mock.run = MagicMock(return_value=_empty_async_gen())
        agent_mock.compaction_count = 0
        return agent_mock

    session = _make_mock_session()

    with (
        patch(
            "cua_bench.agents.openclaw.OpenClawComputerAgent",
            side_effect=fake_openclaw_computer_agent,
        ),
        patch("agent.tools.MilestoneTool", return_value=_make_mock_milestone()),
        patch.object(MemoryStore, "DEFAULT_BASE_DIR", str(mem_base)),
    ):
        from cua_bench.agents.openclaw_agent import OpenClawAgent

        agent = OpenClawAgent(max_steps=5)
        asyncio.run(
            agent.perform_task(
                task_description=task_description,
                session=session,
                logging_dir=logging_dir,
            )
        )

    return captured.get("instructions", "")


class TestSystemPromptIntegration:
    """Capture and verify the full system prompt as the agent would build it."""

    def test_system_prompt_without_task_memory(self, setup):
        """First run — no TASK_MEMORY.md exists. Print the full prompt."""
        logging_dir, mem_base = setup
        prompt = _run_agent(logging_dir, mem_base)

        print("\n" + "=" * 72)
        print("SYSTEM PROMPT (no TASK_MEMORY.md)")
        print("=" * 72)
        print(prompt)
        print("=" * 72)

        # Structural assertions
        assert "## Identity" in prompt
        assert "## Tools" in prompt
        assert "## Current Date & Time" in prompt
        assert "UTC" in prompt
        assert "# Project Context" in prompt
        assert "### AGENTS.md" in prompt
        # Task description is NOT in the system prompt — it's passed via agent.run()
        assert "### task.md" not in prompt
        # No TASK_MEMORY.md injected on first run
        assert "### TASK_MEMORY.md" not in prompt
        # Memory Recall present (memory_search + memory_get are registered)
        assert "## Memory Recall" in prompt
        # Computer + memory tool names present in the rendered prompt summary
        assert "**computer**" in prompt
        assert "**memory_search**" in prompt
        assert "**memory_get**" in prompt
        assert "**memory_write**" in prompt
        assert "Observe the current desktop via screenshots" in prompt

    def test_system_prompt_with_task_memory(self, setup):
        """Second run — TASK_MEMORY.md exists with prior knowledge."""
        logging_dir, mem_base = setup

        # Pre-populate TASK_MEMORY.md
        store = MemoryStore(task_id="mota_24_easy", base_dir=mem_base)
        store.write_task_memory(
            "# Task Knowledge\n\n"
            "- Yellow key is on floor 2, behind the blue door\n"
            "- Use arrow keys to move, not WASD\n"
            "- Save milestone after each floor\n"
        )

        prompt = _run_agent(logging_dir, mem_base)

        print("\n" + "=" * 72)
        print("SYSTEM PROMPT (with TASK_MEMORY.md)")
        print("=" * 72)
        print(prompt)
        print("=" * 72)

        # TASK_MEMORY.md should be injected
        assert "### TASK_MEMORY.md" in prompt
        assert "Yellow key is on floor 2" in prompt
        assert "Use arrow keys to move" in prompt

    def test_memory_session_file_created(self, setup):
        """Verify that init_session() creates a session log file."""
        logging_dir, mem_base = setup
        _run_agent(logging_dir, mem_base, task_description="Test task")

        # Session file should exist under the patched base dir
        memory_dir = mem_base / "tasks" / "mota_24_easy" / "memory"
        assert memory_dir.exists(), f"Expected {memory_dir} to exist"
        session_files = list(memory_dir.glob("session-*.md"))
        assert len(session_files) == 1
        assert session_files[0].name == "session-001.md"

    def test_section_order(self, setup):
        """Verify sections appear in the correct order matching OpenClaw."""
        logging_dir, mem_base = setup
        prompt = _run_agent(logging_dir, mem_base)

        identity_pos = prompt.index("## Identity")
        tools_pos = prompt.index("## Tools")
        time_pos = prompt.index("## Current Date & Time")
        context_pos = prompt.index("# Project Context")

        assert identity_pos < tools_pos < time_pos < context_pos
