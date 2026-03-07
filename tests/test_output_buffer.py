"""Tests for GPU output buffer (Tier 2 programs).

Tests that DON'T need GPU (always run):
- String table building and deduplication
- Output reconstruction from raw buffer data
- Kernel source structural checks

Tests that need MLX (skipped if not available):
- Actual Tier 2 GPU execution with PRINT/PRINTLN
- Tier 1 backward compatibility verification
"""

import struct

import pytest

from emojiasm.parser import parse
from emojiasm.bytecode import (
    compile_to_bytecode,
    gpu_tier,
    _build_string_table,
)
from emojiasm.gpu import (
    get_kernel_source,
    _reconstruct_output,
    _OUTPUT_ENTRY_FIELDS,
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


def _make_entry(thread_id, seq_num, entry_type, value, str_idx=0):
    """Build a raw OutputEntry as a list of 5 uint32 values.

    value is a float; we pack it as uint32 bits for the raw buffer.
    """
    value_bits = struct.unpack('I', struct.pack('f', value))[0]
    return [thread_id, seq_num, entry_type, value_bits, str_idx]


# ── Non-GPU tests (always run) ──────────────────────────────────────────


def test_build_string_table():
    """_build_string_table extracts PRINTS string literals correctly."""
    # PRINTS "hello"
    source = (
        "\U0001f4dc \U0001f3e0\n"
        '  \U0001f4ac "hello"\n'
        "  \U0001f6d1\n"
    )
    program = _parse(source)
    str_map, table = _build_string_table(program)
    assert table == ["hello"]
    assert str_map == {"hello": 0}


def test_string_table_dedup():
    """Same PRINTS literal gets the same index (deduplication)."""
    source = (
        "\U0001f4dc \U0001f3e0\n"
        '  \U0001f4ac "hello"\n'
        '  \U0001f4ac "world"\n'
        '  \U0001f4ac "hello"\n'
        "  \U0001f6d1\n"
    )
    program = _parse(source)
    str_map, table = _build_string_table(program)
    assert table == ["hello", "world"]
    assert str_map["hello"] == 0
    assert str_map["world"] == 1


def test_reconstruct_output():
    """_reconstruct_output correctly sorts and formats float entries."""
    # Two entries from thread 0: value 42 then value 7
    raw = (
        _make_entry(0, 0, 0, 42.0) +
        _make_entry(0, 1, 0, 7.0)
    )
    result = _reconstruct_output(raw, [], 1)
    assert 0 in result
    assert result[0] == "427"


def test_reconstruct_with_newlines():
    """_reconstruct_output handles newline markers correctly."""
    # Thread 0: value 42, newline, value 7, newline
    raw = (
        _make_entry(0, 0, 0, 42.0) +
        _make_entry(0, 1, 2, 0.0) +     # newline
        _make_entry(0, 2, 0, 7.0) +
        _make_entry(0, 3, 2, 0.0)        # newline
    )
    result = _reconstruct_output(raw, [], 1)
    assert result[0] == "42\n7\n"


def test_reconstruct_empty():
    """Empty buffer returns empty outputs dict."""
    result = _reconstruct_output([], [], 1)
    assert result == {}


def test_reconstruct_multiple_threads():
    """Entries from multiple threads are correctly separated."""
    # Thread 0: 42, Thread 1: 99 (interleaved in buffer)
    raw = (
        _make_entry(1, 0, 0, 99.0) +
        _make_entry(0, 0, 0, 42.0)
    )
    result = _reconstruct_output(raw, [], 2)
    assert result[0] == "42"
    assert result[1] == "99"


def test_reconstruct_with_strings():
    """_reconstruct_output handles string table lookups."""
    string_table = ["hello", "world"]
    raw = (
        _make_entry(0, 0, 1, 0.0, 0) +   # string "hello"
        _make_entry(0, 1, 1, 0.0, 1)      # string "world"
    )
    result = _reconstruct_output(raw, string_table, 1)
    assert result[0] == "helloworld"


def test_output_entry_struct_in_kernel():
    """The kernel source should contain the OutputEntry struct definition."""
    src = get_kernel_source()
    assert "struct OutputEntry" in src
    assert "thread_id" in src
    assert "seq_num" in src
    assert "str_idx" in src


def test_output_buffer_bindings_in_kernel():
    """The kernel should have buffer bindings for the output buffer."""
    src = get_kernel_source()
    assert "[[buffer(8)]]" in src
    assert "[[buffer(9)]]" in src
    assert "[[buffer(10)]]" in src
    assert "output_buf" in src
    assert "output_counts" in src
    assert "output_cap" in src


def test_tier2_program_has_string_table():
    """Compiling a Tier 2 program populates the string_table field."""
    source = (
        "\U0001f4dc \U0001f3e0\n"
        "  \U0001f4e5 42\n"
        "  \U0001f4e2\n"   # PRINT
        "  \U0001f6d1\n"
    )
    program = _parse(source)
    assert gpu_tier(program) == 2
    gpu_prog = compile_to_bytecode(program)
    assert gpu_prog.string_table == []  # no PRINTS in this program
    assert gpu_prog.gpu_tier == 2


def test_gpu_tier_classification():
    """Tier classification: 1 for pure numeric, 2 for PRINT/PRINTLN."""
    # Tier 1: just push and halt
    source1 = "\U0001f4dc \U0001f3e0\n  \U0001f4e5 42\n  \U0001f6d1\n"
    assert gpu_tier(_parse(source1)) == 1

    # Tier 2: push, print, halt
    source2 = "\U0001f4dc \U0001f3e0\n  \U0001f4e5 42\n  \U0001f4e2\n  \U0001f6d1\n"
    assert gpu_tier(_parse(source2)) == 2


# ── MLX tests (skipped when MLX not available) ─────────────────────────


@requires_mlx
def test_tier2_print_captures_output():
    """PRINT values are captured in the output buffer on GPU."""
    from emojiasm.gpu import _get_kernel, gpu_run

    _get_kernel.cache_clear()

    # PUSH 42, PRINT, HALT
    source = (
        "\U0001f4dc \U0001f3e0\n"
        "  \U0001f4e5 42\n"
        "  \U0001f4e2\n"   # PRINT
        "  \U0001f6d1\n"
    )
    program = _parse(source)
    result = gpu_run(program, n=4)
    assert result["success"] is True
    assert result["completed"] == 4
    assert "outputs" in result
    # Each thread should have captured "42"
    for tid in range(4):
        assert tid in result["outputs"]
        assert result["outputs"][tid] == "42"


@requires_mlx
def test_tier2_println_has_newlines():
    """PRINTLN adds newline markers to the output buffer."""
    from emojiasm.gpu import _get_kernel, gpu_run

    _get_kernel.cache_clear()

    # PUSH 42, PRINTLN, HALT
    source = (
        "\U0001f4dc \U0001f3e0\n"
        "  \U0001f4e5 42\n"
        "  \U0001f5a8\n"   # PRINTLN
        "  \U0001f6d1\n"
    )
    program = _parse(source)
    result = gpu_run(program, n=2)
    assert result["success"] is True
    assert "outputs" in result
    for tid in range(2):
        assert tid in result["outputs"]
        assert result["outputs"][tid] == "42\n"


@requires_mlx
def test_tier1_still_works():
    """Tier 1 programs are unaffected by output buffer changes."""
    from emojiasm.gpu import _get_kernel, gpu_run

    _get_kernel.cache_clear()

    # PUSH 42, HALT (no PRINT/PRINTLN)
    source = "\U0001f4dc \U0001f3e0\n  \U0001f4e5 42\n  \U0001f6d1\n"
    program = _parse(source)
    result = gpu_run(program, n=10)
    assert result["success"] is True
    assert result["completed"] == 10
    assert all(r == pytest.approx(42.0) for r in result["results"])
    # Tier 1 should NOT have outputs key
    assert "outputs" not in result


@requires_mlx
def test_tier2_multiple_prints():
    """Multiple PRINT calls in one program are all captured."""
    from emojiasm.gpu import _get_kernel, gpu_run

    _get_kernel.cache_clear()

    # PUSH 10, PRINT, PUSH 20, PRINT, PUSH 30, PRINTLN, HALT
    source = (
        "\U0001f4dc \U0001f3e0\n"
        "  \U0001f4e5 10\n"
        "  \U0001f4e2\n"   # PRINT
        "  \U0001f4e5 20\n"
        "  \U0001f4e2\n"   # PRINT
        "  \U0001f4e5 30\n"
        "  \U0001f5a8\n"   # PRINTLN
        "  \U0001f6d1\n"
    )
    program = _parse(source)
    result = gpu_run(program, n=2)
    assert result["success"] is True
    assert "outputs" in result
    for tid in range(2):
        assert result["outputs"][tid] == "102030\n"
