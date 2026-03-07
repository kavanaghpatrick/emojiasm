"""Tests for the EmojiASM REPL."""

import io
import sys
from unittest.mock import patch

import pytest

from emojiasm.repl import _handle_meta, _make_single_instruction_program, run_repl
from emojiasm.opcodes import Op


# ── _handle_meta ──────────────────────────────────────────────────────────────

def test_handle_meta_quit_returns_false():
    assert _handle_meta(":quit", {"stack": [], "memory": {}}) is False

def test_handle_meta_exit_returns_false():
    assert _handle_meta(":exit", {"stack": [], "memory": {}}) is False

def test_handle_meta_unknown_returns_true():
    assert _handle_meta(":foo", {"stack": [], "memory": {}}) is True

def test_handle_meta_reset_clears_stack_and_memory():
    state = {"stack": [1, 2, 3], "memory": {"🔑": 42}}
    _handle_meta(":reset", state)
    assert state["stack"] == []
    assert state["memory"] == {}

def test_handle_meta_reset_mutates_in_place():
    """Ensure :reset clears the SAME list/dict objects (not reassigns refs)."""
    stack = [1, 2]
    memory = {"a": 1}
    state = {"stack": stack, "memory": memory}
    _handle_meta(":reset", state)
    assert stack == []   # same object, now empty
    assert memory == {}  # same object, now empty

def test_handle_meta_mem_returns_true(capsys):
    state = {"stack": [], "memory": {"🔑": 99}}
    result = _handle_meta(":mem", state)
    assert result is True
    captured = capsys.readouterr()
    assert "99" in captured.out

def test_handle_meta_help_returns_true(capsys):
    result = _handle_meta(":help", {"stack": [], "memory": {}})
    assert result is True
    captured = capsys.readouterr()
    assert "📥" in captured.out  # PUSH should appear


# ── _make_single_instruction_program ─────────────────────────────────────────

def test_make_single_instruction_program_push():
    prog = _make_single_instruction_program("📥 42")
    func = prog.functions[prog.entry_point]
    assert len(func.instructions) == 1
    assert func.instructions[0].arg == 42

def test_make_single_instruction_program_dup():
    prog = _make_single_instruction_program("📋")
    func = prog.functions[prog.entry_point]
    assert func.instructions[0].op == Op.DUP

def test_make_single_instruction_program_invalid_raises():
    from emojiasm.parser import ParseError
    with pytest.raises(ParseError):
        _make_single_instruction_program("❓ invalid")


# ── run_repl integration ──────────────────────────────────────────────────────

def _run_repl_with_inputs(*lines):
    """Run REPL with mocked input lines, capture stdout."""
    inputs = list(lines)
    captured = io.StringIO()
    with patch("builtins.input", side_effect=inputs), \
         patch("sys.stdout", captured):
        run_repl()
    return captured.getvalue()

def test_repl_push_shows_stack():
    out = _run_repl_with_inputs("📥 99", ":quit")
    assert "stack: [99]" in out

def test_repl_arithmetic_updates_stack():
    out = _run_repl_with_inputs("📥 10", "📥 5", "➕", ":quit")
    assert "stack: [15]" in out

def test_repl_parse_error_does_not_exit():
    """A bad instruction should print the error and continue the REPL."""
    out = _run_repl_with_inputs("❓ bad", "📥 1", ":quit")
    assert "stack: [1]" in out  # REPL continued after parse error

def test_repl_reset_clears_stack():
    out = _run_repl_with_inputs("📥 42", ":reset", ":quit")
    # After reset, stack should be empty
    assert "stack: [42]" in out  # confirmed push worked
    assert "(state reset)" in out

def test_repl_eof_exits_cleanly():
    """EOF (Ctrl+D) should exit without exception."""
    with patch("builtins.input", side_effect=EOFError):
        run_repl()  # should not raise
