"""Tests for the LLM inference integration module (emojiasm/inference.py)."""

import json
from unittest.mock import patch, MagicMock

import pytest

from emojiasm.inference import EmojiASMTool


# ── Simple programs for testing ──────────────────────────────────────────

# Tier 1: numeric-only (PUSH + ADD + HALT)
SIMPLE_PROGRAM = "\n".join([
    "\U0001f4e5 10",    # PUSH 10
    "\U0001f4e5 20",    # PUSH 20
    "\u2795",           # ADD
    "\U0001f6d1",       # HALT
])

# Tier 2: numeric + output (has PRINTLN)
PRINT_PROGRAM = "\n".join([
    "\U0001f4e5 42",      # PUSH 42
    "\U0001f5a8",         # PRINTLN (no variation selector)
    "\U0001f6d1",         # HALT
])

# Tier 3: has INPUT
INPUT_PROGRAM = "\n".join([
    "\U0001f3a4",         # INPUT
    "\U0001f6d1",         # HALT
])

INVALID_PROGRAM = "not_an_emoji_at_all"

EMPTY_PROGRAM = ""


# ── Initialization tests ────────────────────────────────────────────────

class TestToolInit:
    def test_tool_init_defaults(self):
        tool = EmojiASMTool()
        assert tool.max_instances == 10_000
        assert tool.max_steps == 1_000_000
        assert tool.prefer_gpu is True

    def test_tool_init_custom(self):
        tool = EmojiASMTool(max_instances=500, max_steps=5000, prefer_gpu=False)
        assert tool.max_instances == 500
        assert tool.max_steps == 5000
        assert tool.prefer_gpu is False


# ── Execution tests ─────────────────────────────────────────────────────

class TestExecute:
    def test_execute_simple_cpu(self):
        tool = EmojiASMTool(prefer_gpu=False)
        result = tool.execute(SIMPLE_PROGRAM, n=1)
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["mode"] == "cpu"
        assert result["instances"] == 1
        assert result["completed"] == 1
        assert result["failed"] == 0
        assert isinstance(result["total_time_ms"], float)

    def test_execute_returns_correct_keys(self):
        tool = EmojiASMTool(prefer_gpu=False)
        result = tool.execute(SIMPLE_PROGRAM, n=1)
        expected_keys = {
            "success", "mode", "instances", "completed",
            "failed", "results", "stats", "total_time_ms", "program_tier",
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_execute_caps_instances(self):
        tool = EmojiASMTool(max_instances=5, prefer_gpu=False)
        result = tool.execute(SIMPLE_PROGRAM, n=100)
        assert result["instances"] == 5

    def test_execute_invalid_source(self):
        tool = EmojiASMTool(prefer_gpu=False)
        result = tool.execute(INVALID_PROGRAM, n=1)
        assert result["success"] is False
        assert "error" in result
        assert "Parse error" in result["error"]

    def test_execute_empty_source(self):
        tool = EmojiASMTool(prefer_gpu=False)
        result = tool.execute(EMPTY_PROGRAM, n=1)
        assert result["success"] is False
        assert "error" in result

    def test_execute_print_program(self):
        """Tier 2 program (with PRINTLN) runs on CPU and produces output."""
        tool = EmojiASMTool(prefer_gpu=False)
        result = tool.execute(PRINT_PROGRAM, n=1)
        assert result["success"] is True
        assert result["mode"] == "cpu"
        assert result["program_tier"] == 2


# ── Validation tests ────────────────────────────────────────────────────

class TestValidate:
    def test_validate_valid_program(self):
        tool = EmojiASMTool()
        result = tool.validate(SIMPLE_PROGRAM)
        assert result["valid"] is True
        assert result["error"] is None
        assert result["tier"] in (1, 2, 3)
        assert result["num_instructions"] > 0

    def test_validate_invalid_program(self):
        tool = EmojiASMTool()
        result = tool.validate(INVALID_PROGRAM)
        assert result["valid"] is False
        assert result["error"] is not None
        assert result["gpu_compatible"] is False

    def test_validate_tier_detection(self):
        tool = EmojiASMTool()

        # Tier 1: numeric only
        tier1_result = tool.validate(SIMPLE_PROGRAM)
        assert tier1_result["tier"] == 1
        assert tier1_result["gpu_compatible"] is True

        # Tier 2: has output
        tier2_result = tool.validate(PRINT_PROGRAM)
        assert tier2_result["tier"] == 2
        assert tier2_result["gpu_compatible"] is True

        # Tier 3: has INPUT
        tier3_result = tool.validate(INPUT_PROGRAM)
        assert tier3_result["tier"] == 3
        assert tier3_result["gpu_compatible"] is False

    def test_validate_empty_source(self):
        tool = EmojiASMTool()
        result = tool.validate(EMPTY_PROGRAM)
        assert result["valid"] is False
        assert result["error"] is not None


# ── Tool spec tests ─────────────────────────────────────────────────────

class TestToolSpec:
    def test_as_tool_spec(self):
        tool = EmojiASMTool()
        spec = tool.as_tool_spec()
        assert spec["type"] == "function"
        assert "function" in spec
        func = spec["function"]
        assert func["name"] == "emojiasm_execute"
        assert "description" in func
        assert "parameters" in func
        params = func["parameters"]
        assert params["type"] == "object"
        assert "source" in params["properties"]
        assert "instances" in params["properties"]
        assert "source" in params["required"]


# ── Handle tool call tests ──────────────────────────────────────────────

class TestHandleToolCall:
    def test_handle_tool_call_string_args(self):
        tool = EmojiASMTool(prefer_gpu=False)
        call = {
            "arguments": json.dumps({
                "source": SIMPLE_PROGRAM,
                "instances": 1,
            })
        }
        result = tool.handle_tool_call(call)
        assert isinstance(result, dict)
        assert result["success"] is True

    def test_handle_tool_call_dict_args(self):
        tool = EmojiASMTool(prefer_gpu=False)
        call = {
            "arguments": {
                "source": SIMPLE_PROGRAM,
                "instances": 1,
            }
        }
        result = tool.handle_tool_call(call)
        assert isinstance(result, dict)
        assert result["success"] is True

    def test_handle_tool_call_caps_instances(self):
        tool = EmojiASMTool(max_instances=3, prefer_gpu=False)
        call = {
            "arguments": {
                "source": SIMPLE_PROGRAM,
                "instances": 50,
            }
        }
        result = tool.handle_tool_call(call)
        assert result["instances"] == 3

    def test_handle_tool_call_missing_source(self):
        """When source is missing, should return an error, not crash."""
        tool = EmojiASMTool(prefer_gpu=False)
        call = {"arguments": {}}
        result = tool.handle_tool_call(call)
        assert result["success"] is False


# ── Batch execution tests ───────────────────────────────────────────────

class TestBatch:
    def test_execute_batch(self):
        tool = EmojiASMTool(prefer_gpu=False)
        results = tool.execute_batch([SIMPLE_PROGRAM, PRINT_PROGRAM], n_each=1)
        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is True

    def test_execute_batch_mixed_valid_invalid(self):
        tool = EmojiASMTool(prefer_gpu=False)
        results = tool.execute_batch([SIMPLE_PROGRAM, INVALID_PROGRAM], n_each=1)
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False


# ── GPU routing tests (mocked) ──────────────────────────────────────────

class TestGpuRouting:
    @patch("emojiasm.inference.EmojiASMTool._execute_gpu")
    def test_gpu_routing(self, mock_gpu_exec):
        """Verify GPU is chosen when conditions are met."""
        mock_gpu_exec.return_value = {
            "success": True,
            "mode": "gpu",
            "instances": 256,
            "completed": 256,
            "failed": 0,
            "results": [30.0] * 256,
            "stats": {"mean": 30.0, "std": 0.0, "min": 30.0, "max": 30.0, "count": 256},
            "total_time_ms": 1.0,
            "program_tier": 1,
        }
        tool = EmojiASMTool(prefer_gpu=True)

        # Mock gpu_available to return True
        with patch("emojiasm.gpu.gpu_available", return_value=True):
            result = tool.execute(SIMPLE_PROGRAM, n=256)

        mock_gpu_exec.assert_called_once()
        assert result["mode"] == "gpu"

    def test_cpu_fallback(self):
        """Verify CPU when GPU unavailable."""
        tool = EmojiASMTool(prefer_gpu=True)

        with patch("emojiasm.gpu.gpu_available", return_value=False):
            result = tool.execute(SIMPLE_PROGRAM, n=256)

        assert result["mode"] == "cpu"

    def test_tier3_forces_cpu(self):
        """Programs with INPUT always use CPU."""
        tool = EmojiASMTool(prefer_gpu=True)

        # Even with GPU available, tier 3 should go to CPU
        with patch("emojiasm.gpu.gpu_available", return_value=True):
            result = tool.execute(INPUT_PROGRAM, n=256)

        # INPUT_PROGRAM is tier 3, so the parser will parse it fine,
        # but the routing must choose CPU
        assert result["mode"] == "cpu"

    def test_small_n_uses_cpu(self):
        """n < 256 should always use CPU even when GPU is available."""
        tool = EmojiASMTool(prefer_gpu=True)

        with patch("emojiasm.gpu.gpu_available", return_value=True):
            result = tool.execute(SIMPLE_PROGRAM, n=10)

        assert result["mode"] == "cpu"


# ── Stats helper tests ──────────────────────────────────────────────────

class TestStats:
    def test_stats_empty(self):
        result = EmojiASMTool._compute_stats([])
        assert result["count"] == 0
        assert result["mean"] == 0.0

    def test_stats_single(self):
        result = EmojiASMTool._compute_stats([42.0])
        assert result["count"] == 1
        assert result["mean"] == 42.0
        assert result["std"] == 0.0
        assert result["min"] == 42.0
        assert result["max"] == 42.0

    def test_stats_multiple(self):
        result = EmojiASMTool._compute_stats([10.0, 20.0, 30.0])
        assert result["count"] == 3
        assert result["mean"] == 20.0
        assert result["min"] == 10.0
        assert result["max"] == 30.0
        assert result["std"] > 0
