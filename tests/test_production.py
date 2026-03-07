"""Tests for production robustness (issue #5).

Covers:
  - Arena allocation in compiled C (no malloc in string concat)
  - INPUT_NUM with bad input raises VMError in the VM
  - INPUT_NUM with float input succeeds
  - INPUT_NUM with EOF raises VMError
  - py.typed marker file exists
  - mypy config in pyproject.toml
  - Compiler INPUT_NUM error handling emits stderr/exit
"""

import os
import shutil
import subprocess

import pytest
from unittest.mock import patch

from emojiasm.parser import parse
from emojiasm.compiler import compile_to_c, compile_program
from emojiasm.vm import VM, VMError


clang_available = shutil.which("clang") is not None
requires_clang = pytest.mark.skipif(not clang_available, reason="clang not installed")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(source, max_steps=10000):
    program = parse(source)
    vm = VM(program)
    vm.max_steps = max_steps
    return vm.run()


# ---------------------------------------------------------------------------
# Arena allocation: no malloc in mixed-mode string concat
# ---------------------------------------------------------------------------

def test_arena_alloc_replaces_malloc_in_mixed_mode():
    """Mixed-mode C output must use _arena_alloc, not malloc, for string concat."""
    src = '📜 🏠\n  💬 "hello"\n  💬 " world"\n  ➕\n  📢\n  🛑'
    program = parse(src)
    c_src = compile_to_c(program)
    assert "_arena_alloc" in c_src
    assert "malloc" not in c_src


def test_arena_preamble_present_in_mixed_mode():
    """Mixed-mode C output must include the arena buffer and _arena_alloc function."""
    src = '📜 🏠\n  💬 "x"\n  📢\n  🛑'
    program = parse(src)
    c_src = compile_to_c(program)
    assert "static char _arena[1048576]" in c_src
    assert "static int _arena_pos = 0" in c_src
    assert "_arena_alloc" in c_src


def test_arena_not_in_numeric_only_mode():
    """Numeric-only programs should not include the arena (no strings to allocate)."""
    src = "📜 🏠\n  📥 1\n  📥 2\n  ➕\n  🖨️\n  🛑"
    program = parse(src)
    c_src = compile_to_c(program)
    assert "_arena" not in c_src


@requires_clang
def test_compiled_string_concat_runs_correctly():
    """A string-heavy compiled program should run without crashes (arena allocation)."""
    src = '📜 🏠\n  💬 "hello"\n  💬 " world"\n  ➕\n  📢\n  🛑'
    program = parse(src)
    bin_path = compile_program(program)
    try:
        result = subprocess.run([bin_path], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert result.stdout.strip() == "hello world"
    finally:
        if os.path.exists(bin_path):
            os.unlink(bin_path)


# ---------------------------------------------------------------------------
# INPUT_NUM: bad input raises VMError in VM
# ---------------------------------------------------------------------------

def test_input_num_bad_input_raises_vmerror():
    """INPUT_NUM with non-numeric input must raise VMError."""
    src = """
📜 🏠
  🔟
  🖨️
  🛑
"""
    with patch("builtins.input", return_value="abc"):
        with pytest.raises(VMError, match="Invalid numeric input: abc"):
            run(src)


def test_input_num_float_input_succeeds():
    """INPUT_NUM should accept float input when int() fails."""
    src = """
📜 🏠
  🔟
  🖨️
  🛑
"""
    with patch("builtins.input", return_value="3.14"):
        out = run(src)
    assert "".join(out).strip() == "3.14"


def test_input_num_eof_raises_vmerror():
    """INPUT_NUM with EOF must raise VMError."""
    src = """
📜 🏠
  🔟
  🖨️
  🛑
"""
    with patch("builtins.input", side_effect=EOFError):
        with pytest.raises(VMError, match="Invalid numeric input"):
            run(src)


# ---------------------------------------------------------------------------
# Compiler INPUT_NUM error handling
# ---------------------------------------------------------------------------

def test_compiler_input_num_emits_error_on_bad_scanf():
    """Compiled INPUT_NUM should print error to stderr and exit(1) on bad input."""
    src = "📜 🏠\n  🔟\n  📤\n  🛑"
    program = parse(src)
    c_src = compile_to_c(program)
    assert 'fprintf(stderr,"Invalid numeric input' in c_src
    assert "exit(1)" in c_src


@requires_clang
def test_compiled_input_num_rejects_bad_input():
    """Compiled binary should exit(1) when INPUT_NUM receives non-numeric input."""
    src = "📜 🏠\n  🔟\n  🖨️\n  🛑"
    program = parse(src)
    bin_path = compile_program(program)
    try:
        result = subprocess.run(
            [bin_path], input="not-a-number\n",
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0
        assert "Invalid numeric input" in result.stderr
    finally:
        if os.path.exists(bin_path):
            os.unlink(bin_path)


# ---------------------------------------------------------------------------
# py.typed marker
# ---------------------------------------------------------------------------

def test_py_typed_marker_exists():
    """emojiasm/py.typed must exist as an empty marker file."""
    py_typed = os.path.join(ROOT, "emojiasm", "py.typed")
    assert os.path.isfile(py_typed), f"py.typed not found at {py_typed}"


# ---------------------------------------------------------------------------
# mypy config
# ---------------------------------------------------------------------------

def test_mypy_config_in_pyproject():
    """pyproject.toml must contain [tool.mypy] with expected settings."""
    toml_path = os.path.join(ROOT, "pyproject.toml")
    with open(toml_path) as f:
        content = f.read()
    assert "[tool.mypy]" in content
    assert "mypy_path" in content
    assert "warn_return_any = true" in content
    assert "warn_unused_configs = true" in content
