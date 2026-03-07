"""Tests for the EmojiASM AOT compiler."""

import os
import shutil
import subprocess

import pytest

from emojiasm.parser import parse
from emojiasm.compiler import compile_to_c, compile_program


clang_available = shutil.which("clang") is not None
requires_clang = pytest.mark.skipif(not clang_available, reason="clang not installed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(source: str):
    return parse(source)


# Minimal programs as multiline EmojiASM source strings.
# Directives:
#   📜  = FUNC declaration
#   📥  = PUSH
#   🖨️  = PRINTLN
#   🛑  = HALT
#   💬  = PRINTS (push string literal)
#   💾  = STORE
#   📂  = LOAD
#   🏷️  = LABEL
#   👉  = JMP
#   😤  = JNZ
#   📋  = DUP
#   ➖  = SUB
#   📢  = PRINT (no newline)
#   ➕  = ADD

_PUSH_PRINTLN_HALT = "📜 🏠\n  📥 42\n  🖨️\n  🛑"

_PUSH_STRING_PRINTLN_HALT = "📜 🏠\n  💬 \"hello\"\n  📢\n  🛑"

_NUMERIC_ONLY = "📜 🏠\n  📥 1\n  📥 2\n  ➕\n  🖨️\n  🛑"

_LABEL_PROGRAM = (
    "📜 🏠\n"
    "  📥 3\n"
    "🏷️ loop\n"
    "  📋\n"
    "  🖨️\n"
    "  📥 1\n"
    "  ➖\n"
    "  📋\n"
    "  😤 loop\n"
    "  📤\n"
    "  🛑"
)

# Sum 1..10 using a loop, store accumulator in a memory cell
_SUM_LOOP = (
    "📜 🏠\n"
    "  📥 0\n"
    "  💾 🅰️\n"
    "  📥 10\n"
    "🏷️ top\n"
    "  📋\n"
    "  📂 🅰️\n"
    "  ➕\n"
    "  💾 🅰️\n"
    "  📥 1\n"
    "  ➖\n"
    "  📋\n"
    "  😤 top\n"
    "  📤\n"
    "  📂 🅰️\n"
    "  🖨️\n"
    "  🛑"
)


# ---------------------------------------------------------------------------
# compile_to_c tests (no clang required)
# ---------------------------------------------------------------------------

def test_compile_to_c_returns_string_with_include():
    """compile_to_c must return a string that opens with a C #include."""
    program = _parse(_PUSH_PRINTLN_HALT)
    c_src = compile_to_c(program)
    assert isinstance(c_src, str)
    assert "#include" in c_src


def test_compile_to_c_println_emits_printf():
    """A PUSH+PRINTLN program must reference printf in the C output."""
    program = _parse(_PUSH_PRINTLN_HALT)
    c_src = compile_to_c(program)
    assert "printf" in c_src


def test_compile_to_c_string_program_uses_val_struct():
    """A program with PRINTS must use the mixed-mode preamble with Val struct."""
    program = _parse(_PUSH_STRING_PRINTLN_HALT)
    c_src = compile_to_c(program)
    assert "Val" in c_src


def test_compile_to_c_numeric_only_no_val_struct():
    """A numeric-only program must NOT define the Val struct."""
    program = _parse(_NUMERIC_ONLY)
    c_src = compile_to_c(program)
    assert "Val" not in c_src
    # It should use plain double stack instead
    assert "double" in c_src


def test_compile_to_c_function_name_hex_encoded():
    """Function names are encoded as hex in C identifiers — raw emoji must not appear."""
    program = _parse(_PUSH_PRINTLN_HALT)
    c_src = compile_to_c(program)
    # The home emoji (U+1F3E0) should not appear literally in a fn_ identifier.
    # It's fine if it appears in a comment, but the fn_ prefix is hex-only.
    for line in c_src.splitlines():
        if line.strip().startswith("static void fn_") or line.strip().startswith("fn_"):
            # Identifiers are ASCII; the emoji home glyph must not be in the token
            assert "🏠" not in line.split("(")[0], (
                f"Raw emoji found in function identifier: {line!r}"
            )


def test_compile_to_c_label_emits_goto_and_lbl():
    """A program with a label must produce goto and lbl_ in the C source."""
    program = _parse(_LABEL_PROGRAM)
    c_src = compile_to_c(program)
    assert "goto" in c_src
    assert "lbl_" in c_src


def test_compile_to_c_halt_emits_termination():
    """HALT must compile to an exit() or return statement."""
    program = _parse(_PUSH_PRINTLN_HALT)
    c_src = compile_to_c(program)
    assert "exit(" in c_src or "return" in c_src


def test_compile_to_c_output_is_non_trivial():
    """C output must be a substantive program (> 100 characters)."""
    program = _parse(_PUSH_PRINTLN_HALT)
    c_src = compile_to_c(program)
    assert len(c_src) > 100


# ---------------------------------------------------------------------------
# compile_program tests (require clang)
# ---------------------------------------------------------------------------

@requires_clang
def test_compile_program_push42_println_halt():
    """push 42 + println + halt compiles and prints '42'."""
    program = _parse(_PUSH_PRINTLN_HALT)
    bin_path = compile_program(program)
    try:
        result = subprocess.run([bin_path], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert result.stdout.strip() == "42"
    finally:
        if os.path.exists(bin_path):
            os.unlink(bin_path)


@requires_clang
def test_compile_program_sum_loop():
    """Sum 1..10 loop compiles and produces 55."""
    program = _parse(_SUM_LOOP)
    bin_path = compile_program(program)
    try:
        result = subprocess.run([bin_path], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert result.stdout.strip() == "55"
    finally:
        if os.path.exists(bin_path):
            os.unlink(bin_path)


@requires_clang
def test_compile_program_returns_valid_path():
    """compile_program returns a path to an existing executable before cleanup."""
    program = _parse(_PUSH_PRINTLN_HALT)
    bin_path = compile_program(program)
    try:
        assert os.path.exists(bin_path), (
            f"compile_program returned path that does not exist: {bin_path!r}"
        )
        assert os.access(bin_path, os.X_OK), (
            f"Binary is not executable: {bin_path!r}"
        )
    finally:
        if os.path.exists(bin_path):
            os.unlink(bin_path)


@requires_clang
def test_compile_program_invalid_opt_raises():
    """A bad optimisation flag must raise RuntimeError with 'Compilation failed'."""
    program = _parse(_PUSH_PRINTLN_HALT)
    with pytest.raises(RuntimeError, match="Compilation failed"):
        compile_program(program, opt_level="-totally-invalid-flag-xyz")


# ---------------------------------------------------------------------------
# Mixed-mode codegen coverage
# All ops in a program that contains PRINTS → _uses_strings() = True → Val path
# ---------------------------------------------------------------------------

# A source that puts the compiler in mixed-mode (has 💬 PRINTS) and exercises
# every opcode whose else-branch was not previously covered.
# The program is semantically nonsensical (stack would underflow) but the
# compiler only generates C — it does not execute the program.
_MIXED_ALL_OPS = "\n".join([
    "📜 🏠",
    "  💬 \"x\"",   # PRINTS  — forces mixed mode
    "  📤",          # POP
    "  📥 10",
    "  📥 3",
    "  ➕",          # ADD  (mixed)
    "  📥 3",
    "  ➖",          # SUB  (mixed)
    "  📥 3",
    "  ✖️",          # MUL  (mixed)
    "  📥 3",
    "  ➗",          # DIV  (mixed)
    "  📥 3",
    "  🔢",          # MOD  (mixed)
    "  📋",          # DUP  (shared path)
    "  🔀",          # SWAP (mixed)
    "  🫴",          # OVER (shared path)
    "  🔄",          # ROT  (mixed)
    "  🟰",          # CMP_EQ (mixed)
    "  📏",          # CMP_LT (mixed)
    "  📐",          # CMP_GT (mixed)
    "  🤝",          # AND  (mixed)
    "  🤙",          # OR   (mixed)
    "  🚫",          # NOT  (mixed)
    "  💤",          # NOP
    "  💾 🅰️",      # STORE
    "  📂 🅰️",      # LOAD
    "  📥 0",
    "  🏷️ lbl",
    "  🤔 lbl",      # JZ   (mixed)
    "  😤 lbl",      # JNZ  (mixed)
    "  📞 🏃",      # CALL
    "  🛑",
    "",
    "📜 🏃",
    "  📲",          # RET
])


def _mixed_c():
    return compile_to_c(_parse(_MIXED_ALL_OPS))


def test_mixed_mode_add_uses_snprintf():
    """Mixed-mode ADD must emit the snprintf string-concatenation block."""
    assert "snprintf" in _mixed_c()


def test_mixed_mode_sub_uses_val():
    """Mixed-mode SUB must reference Val fields (a.num - b.num)."""
    c = _mixed_c()
    assert "a.num-b.num" in c or "a.num - b.num" in c


def test_mixed_mode_mul_uses_val():
    assert "a.num*b.num" in _mixed_c() or "a.num * b.num" in _mixed_c()


def test_mixed_mode_div_uses_val():
    assert "a.num" in _mixed_c() and "b.num" in _mixed_c()


def test_mixed_mode_mod_uses_val():
    c = _mixed_c()
    assert "a.num" in c and "b.num" in c


def test_mixed_mode_swap_uses_val():
    """Mixed-mode SWAP must type the temporaries as Val."""
    c = _mixed_c()
    assert "Val b=POP(),a=POP()" in c or "Val b=POP(), a=POP()" in c


def test_mixed_mode_rot_uses_val():
    c = _mixed_c()
    assert "Val c=POP(),b=POP(),a=POP()" in c or "Val c=POP()" in c


def test_mixed_mode_cmp_eq_uses_val():
    c = _mixed_c()
    assert "a.num==b.num" in c


def test_mixed_mode_cmp_lt_uses_val():
    c = _mixed_c()
    assert "a.num<b.num" in c


def test_mixed_mode_cmp_gt_uses_val():
    c = _mixed_c()
    assert "a.num>b.num" in c


def test_mixed_mode_and_uses_val():
    c = _mixed_c()
    assert "a.num&&b.num" in c


def test_mixed_mode_or_uses_val():
    c = _mixed_c()
    assert "a.num||b.num" in c


def test_mixed_mode_not_uses_val():
    c = _mixed_c()
    assert "Val a=POP()" in c


def test_mixed_mode_jz_uses_val():
    c = _mixed_c()
    assert "Val t=POP()" in c and "t.num==0" in c


def test_mixed_mode_jnz_uses_val():
    c = _mixed_c()
    assert "t.num!=0" in c


def test_nop_generates_no_extra_code():
    """NOP must not add any statement — the C line count stays the same."""
    src_with_nop = "📜 🏠\n  📥 1\n  💤\n  🖨️\n  🛑"
    src_without = "📜 🏠\n  📥 1\n  🖨️\n  🛑"
    c_with = compile_to_c(_parse(src_with_nop))
    c_without = compile_to_c(_parse(src_without))
    # NOP emits nothing, so line counts should be identical
    assert len(c_with.splitlines()) == len(c_without.splitlines())


def test_prints_push_string_emits_push_s():
    """PRINTS in mixed mode must emit PUSH_S with the escaped string literal."""
    c = _mixed_c()
    assert 'PUSH_S("x")' in c


def test_input_emits_fgets():
    """INPUT must emit fgets-based stdin reading code."""
    src = "📜 🏠\n  🎤\n  📤\n  🛑"
    c = compile_to_c(_parse(src))
    assert "fgets" in c


def test_input_num_emits_scanf():
    """INPUT_NUM must emit scanf-based number reading code."""
    src = "📜 🏠\n  🔟\n  📤\n  🛑"
    c = compile_to_c(_parse(src))
    assert "scanf" in c
