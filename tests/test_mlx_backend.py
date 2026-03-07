"""Tests for the MLX GPU backend (emojiasm.gpu).

Tests that require MLX are skipped when it is not installed.
Non-MLX tests (stats, tier rejection, CLI parsing, auto-fallback)
always run.
"""

import argparse
import math

import pytest

from emojiasm.parser import parse
from emojiasm.gpu import (
    _stats,
    gpu_available,
    gpu_run,
    run_auto,
)

# ── MLX availability guard ──────────────────────────────────────────────

try:
    import mlx.core as mx

    HAS_MLX = True
except ImportError:
    HAS_MLX = False

requires_mlx = pytest.mark.skipif(not HAS_MLX, reason="MLX not installed")


# ── Helpers ─────────────────────────────────────────────────────────────

def _parse(source: str):
    """Convenience wrapper around parse() for inline EmojiASM source."""
    return parse(source)


# ── Non-MLX tests (always run) ──────────────────────────────────────────


def test_gpu_available_returns_bool():
    """gpu_available() must return a bool and never raise."""
    result = gpu_available()
    assert isinstance(result, bool)


def test_gpu_run_rejects_tier3():
    """Programs with INPUT (tier 3) must raise RuntimeError."""
    source = "\U0001f4dc \U0001f3e0\n  \U0001f3a4\n  \U0001f6d1\n"
    program = _parse(source)
    with pytest.raises(RuntimeError, match="INPUT"):
        gpu_run(program, n=1)


def test_stats_empty():
    """_stats([]) returns all zeros."""
    s = _stats([])
    assert s["mean"] == 0.0
    assert s["std"] == 0.0
    assert s["min"] == 0.0
    assert s["max"] == 0.0
    assert s["count"] == 0


def test_stats_values():
    """_stats([1,2,3,4,5]) computes correct statistics."""
    s = _stats([1.0, 2.0, 3.0, 4.0, 5.0])
    assert s["count"] == 5
    assert s["mean"] == pytest.approx(3.0)
    assert s["std"] == pytest.approx(math.sqrt(2.0))
    assert s["min"] == 1.0
    assert s["max"] == 5.0


def test_auto_fallback_no_gpu(monkeypatch):
    """When GPU is unavailable, run_auto falls back to CPU."""
    monkeypatch.setattr("emojiasm.gpu.gpu_available", lambda: False)
    source = "\U0001f4dc \U0001f3e0\n  \U0001f4e5 42\n  \U0001f6d1\n"
    program = _parse(source)
    result = run_auto(program, n=1)
    assert result["mode"] == "cpu"


def test_cli_gpu_flag_parsed():
    """argparse recognizes --gpu and --gpu-instances."""
    # Import the CLI module to access its argument parser setup
    from emojiasm.__main__ import main  # noqa: F401

    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", default=None)
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--gpu-instances", type=int, default=1)

    args = ap.parse_args(["--gpu", "--gpu-instances", "256", "test.emoji"])
    assert args.gpu is True
    assert args.gpu_instances == 256
    assert args.file == "test.emoji"

    # Also verify the real CLI parser accepts these flags
    args2 = ap.parse_args(["test.emoji"])
    assert args2.gpu is False
    assert args2.gpu_instances == 1


# ── MLX tests (skipped when MLX not available) ─────────────────────────


@requires_mlx
def test_gpu_run_simple():
    """PUSH 42, HALT -> result = 42 on GPU."""
    from emojiasm.gpu import _get_kernel

    _get_kernel.cache_clear()

    source = "\U0001f4dc \U0001f3e0\n  \U0001f4e5 42\n  \U0001f6d1\n"
    program = _parse(source)
    result = gpu_run(program, n=1)
    assert result["success"] is True
    assert result["mode"] == "gpu"
    assert result["completed"] == 1
    assert result["failed"] == 0
    assert result["results"][0] == pytest.approx(42.0)


@requires_mlx
def test_gpu_run_arithmetic():
    """PUSH 6, PUSH 7, MUL, HALT -> result = 42 on GPU."""
    source = (
        "\U0001f4dc \U0001f3e0\n"
        "  \U0001f4e5 6\n"
        "  \U0001f4e5 7\n"
        "  \u2716\ufe0f\n"
        "  \U0001f6d1\n"
    )
    program = _parse(source)
    result = gpu_run(program, n=1)
    assert result["success"] is True
    assert result["results"][0] == pytest.approx(42.0)


@requires_mlx
def test_gpu_run_n_instances():
    """Run with n=100, verify 100 results returned."""
    source = "\U0001f4dc \U0001f3e0\n  \U0001f4e5 7\n  \U0001f6d1\n"
    program = _parse(source)
    result = gpu_run(program, n=100)
    assert result["success"] is True
    assert result["instances"] == 100
    assert result["completed"] == 100
    assert len(result["results"]) == 100
    assert all(r == pytest.approx(7.0) for r in result["results"])


@requires_mlx
def test_gpu_run_monte_carlo():
    """Monte Carlo pi with n=1000: mean result should approximate pi."""
    # Tier 1 Monte Carlo pi (no PRINTLN, leaves result on stack)
    source = (
        "\U0001f4dc \U0001f3e0\n"
        "  \U0001f4e5 0\n"
        "  \U0001f4be \U0001f522\n"  # STORE hits
        "  \U0001f4e5 0\n"
        "  \U0001f4be \U0001f4ca\n"  # STORE counter
        "  \U0001f4e5 10000\n"
        "  \U0001f4be \U0001f3af\n"  # STORE total
        "\n"
        "  \U0001f3f7\ufe0f \U0001f501\n"  # LABEL loop
        "    \U0001f4c2 \U0001f4ca\n"  # LOAD counter
        "    \U0001f4c2 \U0001f3af\n"  # LOAD total
        "    \U0001f7f0\n"  # CMP_EQ
        "    \U0001f624 \U0001f3c1\n"  # JNZ done
        "\n"
        "    \U0001f3b2\n"  # RANDOM
        "    \U0001f4cb\n"  # DUP
        "    \u2716\ufe0f\n"  # MUL (x*x)
        "    \U0001f3b2\n"  # RANDOM
        "    \U0001f4cb\n"  # DUP
        "    \u2716\ufe0f\n"  # MUL (y*y)
        "    \u2795\n"  # ADD (x*x + y*y)
        "    \U0001f4e5 1.0\n"  # PUSH 1.0
        "    \U0001f4d0\n"  # CMP_GT
        "    \U0001f6ab\n"  # NOT (1 if inside circle)
        "    \U0001f914 \u2b55\n"  # JZ skip
        "    \U0001f4c2 \U0001f522\n"  # LOAD hits
        "    \U0001f4e5 1\n"  # PUSH 1
        "    \u2795\n"  # ADD
        "    \U0001f4be \U0001f522\n"  # STORE hits
        "    \U0001f3f7\ufe0f \u2b55\n"  # LABEL skip
        "\n"
        "    \U0001f4c2 \U0001f4ca\n"  # LOAD counter
        "    \U0001f4e5 1\n"  # PUSH 1
        "    \u2795\n"  # ADD
        "    \U0001f4be \U0001f4ca\n"  # STORE counter
        "    \U0001f449 \U0001f501\n"  # JMP loop
        "\n"
        "  \U0001f3f7\ufe0f \U0001f3c1\n"  # LABEL done
        "  \U0001f4c2 \U0001f522\n"  # LOAD hits
        "  \U0001f4e5 4.0\n"  # PUSH 4.0
        "  \u2716\ufe0f\n"  # MUL
        "  \U0001f4c2 \U0001f3af\n"  # LOAD total
        "  \u2797\n"  # DIV
        "  \U0001f6d1\n"  # HALT
    )
    program = _parse(source)
    result = gpu_run(program, n=1000, max_steps=10_000_000)
    assert result["success"] is True
    assert result["completed"] == 1000
    # Each instance estimates pi independently; mean should be close to pi
    mean_pi = result["stats"]["mean"]
    assert mean_pi == pytest.approx(math.pi, abs=0.1)
