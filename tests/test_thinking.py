"""Unit tests for OpenClaw thinking level system (US-OC-019).

Tests:
  - ThinkLevel enum values match OpenClaw's 7 levels
  - resolve_thinking_default() model capability detection
  - resolve_thinking_params() provider-specific parameter mapping
  - ThinkingConfig per-call-site params (flush/compaction independent of main level)
"""

import pytest

from cua_bench.agents.openclaw.thinking import (
    ThinkingConfig,
    ThinkLevel,
    resolve_thinking_default,
    resolve_thinking_params,
)


# ---------------------------------------------------------------------------
# ThinkLevel enum
# ---------------------------------------------------------------------------


class TestThinkLevel:
    def test_all_seven_levels_exist(self):
        """ThinkLevel has exactly the 7 levels from OpenClaw."""
        expected = {"off", "minimal", "low", "medium", "high", "xhigh", "adaptive"}
        actual = {level.value for level in ThinkLevel}
        assert actual == expected

    def test_string_enum(self):
        """ThinkLevel values are usable as strings."""
        assert ThinkLevel.HIGH == "high"
        assert ThinkLevel("medium") == ThinkLevel.MEDIUM

    def test_invalid_level_raises(self):
        with pytest.raises(ValueError):
            ThinkLevel("turbo")


# ---------------------------------------------------------------------------
# resolve_thinking_default — model capability detection
# ---------------------------------------------------------------------------


class TestResolveThinkingDefault:
    def test_claude_46_opus_adaptive(self):
        assert resolve_thinking_default("anthropic/claude-opus-4-6-20260101") == ThinkLevel.ADAPTIVE

    def test_claude_46_sonnet_adaptive(self):
        assert resolve_thinking_default("anthropic/claude-sonnet-4-6-20260101") == ThinkLevel.ADAPTIVE

    def test_claude_45_opus_adaptive(self):
        """Claude Opus 4.5 also matches the 4.6 pattern."""
        assert resolve_thinking_default("anthropic/claude-opus-4-5-20250929") == ThinkLevel.ADAPTIVE

    def test_claude_4_sonnet_low(self):
        assert resolve_thinking_default("anthropic/claude-sonnet-4-20250514") == ThinkLevel.LOW

    def test_claude_haiku_45_low(self):
        assert resolve_thinking_default("anthropic/claude-haiku-4-5-20251001") == ThinkLevel.LOW

    def test_deepseek_r1_low(self):
        assert resolve_thinking_default("deepseek/deepseek-r1") == ThinkLevel.LOW

    def test_openai_o3_low(self):
        assert resolve_thinking_default("openai/o3-mini") == ThinkLevel.LOW

    def test_gpt_4o_off(self):
        assert resolve_thinking_default("openai/gpt-4o") == ThinkLevel.OFF

    def test_unknown_model_off(self):
        assert resolve_thinking_default("some-provider/random-model") == ThinkLevel.OFF


# ---------------------------------------------------------------------------
# resolve_thinking_params — provider-specific mapping
# ---------------------------------------------------------------------------


class TestResolveThinkingParams:
    def test_off_returns_empty(self):
        assert resolve_thinking_params(ThinkLevel.OFF, "anthropic/claude-sonnet-4-20250514") == {}

    # Anthropic
    def test_anthropic_minimal(self):
        result = resolve_thinking_params(ThinkLevel.MINIMAL, "anthropic/claude-sonnet-4-6-20260101")
        assert result == {"thinking": {"type": "enabled", "budget_tokens": 2000}}

    def test_anthropic_high(self):
        result = resolve_thinking_params(ThinkLevel.HIGH, "anthropic/claude-opus-4-6-20260101")
        assert result == {"thinking": {"type": "enabled", "budget_tokens": 16000}}

    def test_anthropic_adaptive(self):
        result = resolve_thinking_params(ThinkLevel.ADAPTIVE, "anthropic/claude-sonnet-4-6-20260101")
        assert result == {"thinking": {"type": "enabled", "budget_tokens": 10000}}

    def test_anthropic_xhigh(self):
        result = resolve_thinking_params(ThinkLevel.XHIGH, "anthropic/claude-opus-4-6-20260101")
        assert result == {"thinking": {"type": "enabled", "budget_tokens": 25000}}

    # OpenAI
    def test_openai_medium(self):
        result = resolve_thinking_params(ThinkLevel.MEDIUM, "openai/gpt-4o")
        assert result == {"reasoning": {"effort": "medium", "summary": "concise"}}

    def test_openai_high(self):
        result = resolve_thinking_params(ThinkLevel.HIGH, "openai/gpt-5.4")
        assert result == {"reasoning": {"effort": "high", "summary": "concise"}}

    def test_openai_low(self):
        result = resolve_thinking_params(ThinkLevel.LOW, "openai/computer-use-preview")
        assert result == {"reasoning": {"effort": "low", "summary": "concise"}}

    def test_openai_chat_transport_uses_reasoning_effort(self):
        result = resolve_thinking_params(
            ThinkLevel.HIGH,
            "openai/gpt-5.4",
            transport="chat",
        )
        assert result == {"reasoning_effort": "high"}

    # Gemini
    def test_gemini_medium(self):
        result = resolve_thinking_params(ThinkLevel.MEDIUM, "google/gemini-3-pro")
        assert result == {"thinking_level": "MEDIUM"}

    def test_gemini_high(self):
        result = resolve_thinking_params(ThinkLevel.HIGH, "vertex_ai/gemini-3-flash")
        assert result == {"thinking_level": "HIGH"}

    # Fallback
    def test_fallback_reasoning_effort(self):
        result = resolve_thinking_params(ThinkLevel.MEDIUM, "some-provider/some-model")
        assert result == {"reasoning_effort": "medium"}


# ---------------------------------------------------------------------------
# ThinkingConfig
# ---------------------------------------------------------------------------


class TestThinkingConfig:
    def test_default_all_off(self):
        cfg = ThinkingConfig()
        assert cfg.level == ThinkLevel.OFF
        assert cfg.flush_level == ThinkLevel.OFF
        assert cfg.compaction_level == ThinkLevel.OFF
        assert cfg.vision_level == ThinkLevel.OFF

    def test_main_level_params(self):
        cfg = ThinkingConfig(level=ThinkLevel.HIGH)
        result = cfg.to_api_params("anthropic/claude-sonnet-4-6-20260101")
        assert result == {"thinking": {"type": "enabled", "budget_tokens": 16000}}

    def test_flush_independent_of_main(self):
        """Flush level produces its own params, independent of main level."""
        cfg = ThinkingConfig(level=ThinkLevel.HIGH, flush_level=ThinkLevel.MINIMAL)
        flush = cfg.flush_params("anthropic/claude-sonnet-4-6-20260101")
        assert flush == {"thinking": {"type": "enabled", "budget_tokens": 2000}}

    def test_compaction_independent_of_main(self):
        """Compaction level produces its own params, independent of main level."""
        cfg = ThinkingConfig(level=ThinkLevel.XHIGH, compaction_level=ThinkLevel.OFF)
        compact = cfg.compaction_params("anthropic/claude-sonnet-4-6-20260101")
        assert compact == {}

    def test_off_main_with_active_flush(self):
        """Main loop off but flush active — valid configuration."""
        cfg = ThinkingConfig(level=ThinkLevel.OFF, flush_level=ThinkLevel.LOW)
        assert cfg.to_api_params("anthropic/claude-sonnet-4-6-20260101") == {}
        assert cfg.flush_params("anthropic/claude-sonnet-4-6-20260101") == {
            "thinking": {"type": "enabled", "budget_tokens": 5000}
        }

    def test_openai_helper_paths_use_reasoning_effort(self):
        cfg = ThinkingConfig(
            level=ThinkLevel.HIGH,
            flush_level=ThinkLevel.HIGH,
            compaction_level=ThinkLevel.HIGH,
            vision_level=ThinkLevel.HIGH,
        )
        assert cfg.to_api_params("openai/gpt-5.4") == {
            "reasoning": {"effort": "high", "summary": "concise"}
        }
        assert cfg.flush_params("openai/gpt-5.4") == {
            "reasoning": {"effort": "high", "summary": "concise"}
        }
        assert cfg.compaction_params("openai/gpt-5.4") == {"reasoning_effort": "high"}
        assert cfg.vision_params("openai/gpt-5.4") == {"reasoning_effort": "high"}

    def test_flush_and_compaction_can_inherit_main_level(self):
        """When set to the same level, auxiliary call sites match the main params."""
        cfg = ThinkingConfig(
            level=ThinkLevel.MEDIUM,
            flush_level=ThinkLevel.MEDIUM,
            compaction_level=ThinkLevel.MEDIUM,
        )
        expected = {"thinking": {"type": "enabled", "budget_tokens": 10000}}
        assert cfg.to_api_params("anthropic/claude-sonnet-4-6-20260101") == expected
        assert cfg.flush_params("anthropic/claude-sonnet-4-6-20260101") == expected
        assert cfg.compaction_params("anthropic/claude-sonnet-4-6-20260101") == expected

    def test_vision_defaults_off_even_when_main_is_enabled(self):
        cfg = ThinkingConfig(level=ThinkLevel.HIGH, flush_level=ThinkLevel.HIGH)
        assert cfg.vision_params("anthropic/claude-sonnet-4-6-20260101") == {}
