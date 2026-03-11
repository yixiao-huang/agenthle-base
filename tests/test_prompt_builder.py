"""Tests for PromptBuilder — US-OC-001: System Prompt Builder."""

import sys
from pathlib import Path

# Add the CUA bench package to the path so we can import the openclaw module
sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parent.parent
        / "submodules"
        / "cua"
        / "libs"
        / "cua-bench"
    ),
)

from cua_bench.agents.openclaw import ContextFile, PromptBuilder, PromptConfig, SectionConfig


class TestPromptBuilderSections:
    """Test that build() returns a string with labeled sections."""

    def test_default_build_has_identity(self):
        builder = PromptBuilder()
        result = builder.build()
        assert "## Identity" in result

    def test_build_with_tools_has_tools_section(self):
        builder = PromptBuilder()
        tools = {"computer": "Mouse and keyboard control", "save_milestone_screenshot": "Save a screenshot"}
        result = builder.build(tool_summaries=tools)
        assert "## Identity" in result
        assert "## Tools" in result

    def test_build_with_memory_tools_has_memory_section(self):
        builder = PromptBuilder()
        tools = {
            "computer": "Mouse and keyboard control",
            "memory_search": "Search memory files",
            "memory_get": "Read a memory file",
        }
        result = builder.build(tool_summaries=tools)
        assert "## Memory Recall" in result

    def test_build_with_context_files_has_project_context(self):
        builder = PromptBuilder()
        files = [ContextFile(path="AGENTS.md", content="Agent guidance content")]
        result = builder.build(context_files=files)
        assert "# Project Context" in result
        assert "## AGENTS.md" in result

    def test_full_build_has_all_sections_in_order(self):
        builder = PromptBuilder()
        tools = {
            "computer": "Mouse and keyboard control",
            "memory_search": "Search memory files",
        }
        files = [ContextFile(path="AGENTS.md", content="guidance")]
        result = builder.build(tool_summaries=tools, context_files=files)

        # Verify section order
        identity_pos = result.index("## Identity")
        tools_pos = result.index("## Tools")
        memory_pos = result.index("## Memory Recall")
        context_pos = result.index("# Project Context")

        assert identity_pos < tools_pos < memory_pos < context_pos


class TestDisabledSections:
    """Test that disabled sections produce no output."""

    def test_disable_identity(self):
        config = PromptConfig(identity=SectionConfig(enabled=False))
        builder = PromptBuilder(config)
        result = builder.build()
        assert "## Identity" not in result

    def test_disable_tools(self):
        config = PromptConfig(tools=SectionConfig(enabled=False))
        builder = PromptBuilder(config)
        tools = {"computer": "Mouse and keyboard control"}
        result = builder.build(tool_summaries=tools)
        assert "## Tools" not in result

    def test_disable_memory(self):
        config = PromptConfig(memory=SectionConfig(enabled=False))
        builder = PromptBuilder(config)
        tools = {"memory_search": "Search memory files"}
        result = builder.build(tool_summaries=tools)
        assert "## Memory Recall" not in result

    def test_disable_project_context(self):
        config = PromptConfig(project_context=SectionConfig(enabled=False))
        builder = PromptBuilder(config)
        files = [ContextFile(path="AGENTS.md", content="content")]
        result = builder.build(context_files=files)
        assert "# Project Context" not in result

    def test_all_disabled_returns_empty(self):
        config = PromptConfig(
            identity=SectionConfig(enabled=False),
            tools=SectionConfig(enabled=False),
            memory=SectionConfig(enabled=False),
            project_context=SectionConfig(enabled=False),
        )
        builder = PromptBuilder(config)
        tools = {"computer": "control", "memory_search": "search"}
        files = [ContextFile(path="test.md", content="test")]
        result = builder.build(tool_summaries=tools, context_files=files)
        assert result == ""

    def test_each_section_independently_disableable(self):
        """Each section can be independently enabled/disabled."""
        tools = {"computer": "control", "memory_search": "search"}
        files = [ContextFile(path="test.md", content="test")]

        sections = ["identity", "tools", "memory", "project_context"]
        markers = ["## Identity", "## Tools", "## Memory Recall", "# Project Context"]

        for i, section in enumerate(sections):
            kwargs = {section: SectionConfig(enabled=False)}
            config = PromptConfig(**kwargs)
            builder = PromptBuilder(config)
            result = builder.build(tool_summaries=tools, context_files=files)
            assert markers[i] not in result, f"Section {section} should be disabled"
            # Other sections should still be present
            for j, marker in enumerate(markers):
                if j != i:
                    assert marker in result, f"Section {sections[j]} should still be enabled"


class TestToolsSection:
    """Test that tool names and descriptions appear in the Tools section."""

    def test_tool_names_in_output(self):
        builder = PromptBuilder()
        tools = {
            "computer": "Mouse and keyboard control",
            "save_milestone_screenshot": "Save a screenshot checkpoint",
        }
        result = builder.build(tool_summaries=tools)
        assert "**computer**" in result
        assert "**save_milestone_screenshot**" in result

    def test_tool_descriptions_in_output(self):
        builder = PromptBuilder()
        tools = {"computer": "Mouse and keyboard control"}
        result = builder.build(tool_summaries=tools)
        assert "Mouse and keyboard control" in result

    def test_no_tools_section_when_empty(self):
        builder = PromptBuilder()
        result = builder.build(tool_summaries={})
        assert "## Tools" not in result

    def test_no_tools_section_when_none(self):
        builder = PromptBuilder()
        result = builder.build(tool_summaries=None)
        assert "## Tools" not in result


class TestMemorySection:
    """Test Memory Recall section behavior."""

    def test_memory_omitted_when_no_memory_tools(self):
        builder = PromptBuilder()
        tools = {"computer": "control", "save_milestone_screenshot": "save"}
        result = builder.build(tool_summaries=tools)
        assert "## Memory Recall" not in result

    def test_memory_present_with_memory_search(self):
        builder = PromptBuilder()
        tools = {"computer": "control", "memory_search": "Search memory"}
        result = builder.build(tool_summaries=tools)
        assert "## Memory Recall" in result

    def test_memory_present_with_memory_get(self):
        builder = PromptBuilder()
        tools = {"memory_get": "Read a memory file"}
        result = builder.build(tool_summaries=tools)
        assert "## Memory Recall" in result

    def test_memory_not_triggered_by_non_recall_tools(self):
        """Only memory_search and memory_get trigger Memory Recall (matching OpenClaw)."""
        builder = PromptBuilder()
        tools = {"memory_write": "Write to memory"}
        result = builder.build(tool_summaries=tools)
        assert "## Memory Recall" not in result

    def test_memory_mentions_search_first_directive(self):
        """Memory section should have search-first behavioral directive like OpenClaw."""
        builder = PromptBuilder()
        tools = {"memory_search": "search", "memory_get": "get"}
        result = builder.build(tool_summaries=tools)
        assert "memory_search" in result
        assert "memory_get" in result


class TestProjectContext:
    """Test Project Context injection."""

    def test_context_file_content_injected(self):
        builder = PromptBuilder()
        files = [ContextFile(path="AGENTS.md", content="You are an agent.")]
        result = builder.build(context_files=files)
        assert "You are an agent." in result

    def test_context_file_path_as_header(self):
        builder = PromptBuilder()
        files = [ContextFile(path="AGENTS.md", content="content")]
        result = builder.build(context_files=files)
        assert "## AGENTS.md" in result

    def test_empty_context_files_omits_section(self):
        builder = PromptBuilder()
        result = builder.build(context_files=[])
        assert "# Project Context" not in result

    def test_multiple_context_files_in_order(self):
        builder = PromptBuilder()
        files = [
            ContextFile(path="AGENTS.md", content="Agent guidance"),
            ContextFile(path="task.md", content="Task description"),
            ContextFile(path="MEMORY.md", content="Memory content"),
        ]
        result = builder.build(context_files=files)

        agents_pos = result.index("## AGENTS.md")
        task_pos = result.index("## task.md")
        memory_pos = result.index("## MEMORY.md")

        assert agents_pos < task_pos < memory_pos

    def test_multiple_context_files_all_content_present(self):
        builder = PromptBuilder()
        files = [
            ContextFile(path="AGENTS.md", content="Agent guidance here"),
            ContextFile(path="task.md", content="Complete the puzzle"),
        ]
        result = builder.build(context_files=files)
        assert "Agent guidance here" in result
        assert "Complete the puzzle" in result

    def test_context_header_text(self):
        builder = PromptBuilder()
        files = [ContextFile(path="test.md", content="test")]
        result = builder.build(context_files=files)
        assert "The following project context files have been loaded:" in result
