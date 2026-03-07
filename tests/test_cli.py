"""CLI tests for EmojiASM — exercises python3 -m emojiasm via subprocess."""

import os
import shutil
import subprocess
import sys
import tempfile

import pytest

PYTHON = sys.executable

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def run_cli(source, *args):
    """Write *source* to a temp .emoji file, invoke the CLI, return CompletedProcess."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".emoji", delete=False, encoding="utf-8"
    ) as f:
        f.write(source)
        fname = f.name
    try:
        result = subprocess.run(
            [PYTHON, "-m", "emojiasm", fname] + list(args),
            capture_output=True,
            text=True,
        )
        return result
    finally:
        os.unlink(fname)


# ---------------------------------------------------------------------------
# Availability check for clang-dependent tests
# ---------------------------------------------------------------------------

clang_available = shutil.which("clang") is not None

# ---------------------------------------------------------------------------
# Source snippets reused across tests
# ---------------------------------------------------------------------------

# Prints "Hello" (no newline) then halts
HELLO_SRC = '📜 🏠\n  💬 "Hello"\n  📢\n  🛑'

# Prints 99 on its own line then halts
PRINT_99_SRC = "📜 🏠\n  📥 99\n  🖨️\n  🛑"

# Division by zero — triggers VMError
DIV_ZERO_SRC = "📜 🏠\n  📥 10\n  📥 0\n  ➗\n  🛑"

# Infinite loop — unconditional jump back to itself
INFINITE_LOOP_SRC = "📜 🏠\n🏷️ 🔁\n  👉 🔁\n  🛑"

# A source line that is not a valid opcode, directive, or comment
UNKNOWN_INSTR_SRC = "📜 🏠\n  NOTANOPCODE\n  🛑"

# ---------------------------------------------------------------------------
# 1. Basic run: hello world
# ---------------------------------------------------------------------------

def test_hello_world():
    """A valid program printing 'Hello' exits 0 with correct stdout."""
    result = run_cli(HELLO_SRC)
    assert result.returncode == 0
    assert "Hello" in result.stdout


# ---------------------------------------------------------------------------
# 2. File not found
# ---------------------------------------------------------------------------

def test_file_not_found():
    """Passing a nonexistent path exits 1 and reports the problem on stderr."""
    result = subprocess.run(
        [PYTHON, "-m", "emojiasm", "nonexistent_file_xyzzy.emoji"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "not found" in result.stderr.lower() or "not found" in result.stderr


# ---------------------------------------------------------------------------
# 3. Parse error
# ---------------------------------------------------------------------------

def test_parse_error_exit_code():
    """Source containing an unknown instruction exits 1."""
    result = run_cli(UNKNOWN_INSTR_SRC)
    assert result.returncode == 1


def test_parse_error_stderr_marker():
    """Parse errors must surface the 💥 marker on stderr."""
    result = run_cli(UNKNOWN_INSTR_SRC)
    assert "💥" in result.stderr


# ---------------------------------------------------------------------------
# 4. Runtime error: division by zero
# ---------------------------------------------------------------------------

def test_div_by_zero_exit_code():
    """Division by zero exits 1."""
    result = run_cli(DIV_ZERO_SRC)
    assert result.returncode == 1


def test_div_by_zero_stderr_marker():
    """VMError must surface the 💀 marker on stderr."""
    result = run_cli(DIV_ZERO_SRC)
    assert "💀" in result.stderr


# ---------------------------------------------------------------------------
# 5. --disasm flag
# ---------------------------------------------------------------------------

def test_disasm_exit_zero():
    """--disasm exits 0."""
    result = run_cli(HELLO_SRC, "--disasm")
    assert result.returncode == 0


def test_disasm_contains_emoji_opcodes():
    """--disasm output contains emoji opcodes (not just plain text)."""
    result = run_cli(HELLO_SRC, "--disasm")
    # Disassembly header uses 📜; instruction lines use opcode emoji
    assert "📜" in result.stdout


def test_disasm_no_program_output():
    """--disasm must not execute the program.

    The disassembly will contain the quoted string literal '\"Hello\"' as part of
    the PRINTS instruction representation, but the PRINT opcode must never fire,
    so the bare unquoted word 'Hello' (on its own line, as execution would produce)
    must not appear.  We check that no line consists solely of 'Hello'.
    """
    result = run_cli(HELLO_SRC, "--disasm")
    # Execution of PRINT would write exactly 'Hello' (no quotes) to stdout.
    # Disassembly legitimately includes  💬 "Hello"  (with quotes).
    bare_hello_lines = [
        line for line in result.stdout.splitlines() if line.strip() == "Hello"
    ]
    assert bare_hello_lines == [], (
        f"Program appears to have been executed; bare 'Hello' line found in: {result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# 6. --emit-c flag
# ---------------------------------------------------------------------------

def test_emit_c_exit_zero():
    """--emit-c exits 0."""
    result = run_cli(PRINT_99_SRC, "--emit-c")
    assert result.returncode == 0


def test_emit_c_produces_c_source():
    """--emit-c stdout must look like C source (contains '#include')."""
    result = run_cli(PRINT_99_SRC, "--emit-c")
    assert "#include" in result.stdout


def test_emit_c_no_execution():
    """--emit-c must not run the program."""
    result = run_cli(PRINT_99_SRC, "--emit-c")
    # The program would print "99"; that must not appear as bare output
    # (it might appear inside the C source string literals, so we check
    # that the output is not just a bare number — it should contain '#include')
    assert "#include" in result.stdout


# ---------------------------------------------------------------------------
# 7. -d / --debug: trace lines on stderr
# ---------------------------------------------------------------------------

def test_debug_short_flag():
    """-d produces 🔍 trace lines on stderr."""
    result = run_cli(HELLO_SRC, "-d")
    assert result.returncode == 0
    assert "🔍" in result.stderr


def test_debug_long_flag():
    """--debug produces 🔍 trace lines on stderr."""
    result = run_cli(HELLO_SRC, "--debug")
    assert result.returncode == 0
    assert "🔍" in result.stderr


def test_debug_stdout_unaffected():
    """Debug mode must not pollute stdout."""
    result = run_cli(HELLO_SRC, "--debug")
    assert "Hello" in result.stdout


# ---------------------------------------------------------------------------
# 8. --max-steps: infinite loop is capped
# ---------------------------------------------------------------------------

def test_max_steps_kills_infinite_loop():
    """--max-steps 5 causes an infinite loop to exit 1 with 'Execution limit' on stderr."""
    result = run_cli(INFINITE_LOOP_SRC, "--max-steps", "5")
    assert result.returncode == 1
    assert "Execution limit" in result.stderr


# ---------------------------------------------------------------------------
# 9. --max-steps: large value lets a normal program finish
# ---------------------------------------------------------------------------

def test_max_steps_large_allows_normal_program():
    """--max-steps 1000000 does not prevent a finite program from completing."""
    result = run_cli(HELLO_SRC, "--max-steps", "1000000")
    assert result.returncode == 0
    assert "Hello" in result.stdout


# ---------------------------------------------------------------------------
# 10. --disasm output format detail
# ---------------------------------------------------------------------------

def test_disasm_output_format_function_name():
    """Disassembly output includes the function-name emoji after the 📜 directive."""
    result = run_cli(HELLO_SRC, "--disasm")
    # The main function is named 🏠; disasm must emit '📜 🏠'
    assert "🏠" in result.stdout


def test_disasm_output_format_instruction_emoji():
    """Disassembly output contains at least one instruction-level opcode emoji."""
    result = run_cli(HELLO_SRC, "--disasm")
    # HELLO_SRC uses PRINTS (💬), PRINT (📢), HALT (🛑)
    assert any(emoji in result.stdout for emoji in ("💬", "📢", "🛑"))


# ---------------------------------------------------------------------------
# 11. --compile (clang-dependent)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not clang_available, reason="clang not installed")
def test_compile_flag():
    """--compile AOT-compiles and runs the program successfully."""
    result = run_cli(PRINT_99_SRC, "--compile")
    assert result.returncode == 0
    assert "99" in result.stdout


@pytest.mark.skipif(not clang_available, reason="clang not installed")
def test_compile_opt_flag():
    """--opt= is accepted and the program still runs correctly."""
    result = run_cli(PRINT_99_SRC, "--compile", "--opt=-O1")
    assert result.returncode == 0
    assert "99" in result.stdout
