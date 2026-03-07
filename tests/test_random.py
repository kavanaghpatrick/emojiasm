"""Tests for the RANDOM opcode (🎲)."""

import os
import subprocess
import tempfile

from emojiasm.opcodes import Op, EMOJI_TO_OP, OP_TO_EMOJI
from emojiasm.parser import parse
from emojiasm.vm import VM
from emojiasm.compiler import compile_to_c
from emojiasm.disasm import disassemble


def run(source: str, max_steps: int = 100_000) -> list[str]:
    program = parse(source)
    vm = VM(program)
    vm.max_steps = max_steps
    return vm.run()


# ── Opcode registration ──────────────────────────────────────────────────


def test_random_in_op_enum():
    assert hasattr(Op, "RANDOM")
    assert isinstance(Op.RANDOM, Op)


def test_random_emoji_to_op():
    assert "\U0001f3b2" in EMOJI_TO_OP  # 🎲
    assert EMOJI_TO_OP["\U0001f3b2"] == Op.RANDOM


def test_random_op_to_emoji():
    assert Op.RANDOM in OP_TO_EMOJI
    assert OP_TO_EMOJI[Op.RANDOM] == "\U0001f3b2"


# ── Parser ────────────────────────────────────────────────────────────────


def test_parser_recognises_dice():
    prog = parse("📜 🏠\n  🎲\n  🛑")
    func = prog.functions["🏠"]
    assert func.instructions[0].op == Op.RANDOM


def test_parser_random_no_arg():
    prog = parse("📜 🏠\n  🎲\n  🛑")
    func = prog.functions["🏠"]
    assert func.instructions[0].arg is None


# ── VM execution ──────────────────────────────────────────────────────────


def test_vm_random_pushes_float():
    """RANDOM pushes a float onto the stack."""
    source = "📜 🏠\n  🎲\n  🖨️\n  🛑"
    out = run(source)
    val = float("".join(out).strip())
    assert isinstance(val, float)


def test_vm_random_range():
    """RANDOM pushes a value in [0.0, 1.0)."""
    source = "📜 🏠\n  🎲\n  🖨️\n  🛑"
    for _ in range(50):
        out = run(source)
        val = float("".join(out).strip())
        assert 0.0 <= val < 1.0


def test_vm_random_stack_effect():
    """RANDOM has stack effect ( -- n ): pushes exactly one value."""
    prog = parse("📜 🏠\n  🎲\n  🛑")
    vm = VM(prog)
    vm.run()
    assert len(vm.stack) == 1
    assert isinstance(vm.stack[0], float)


def test_vm_random_not_always_same():
    """Two separate runs produce at least one different value in 20 trials."""
    source = "📜 🏠\n  🎲\n  🖨️\n  🛑"
    values = set()
    for _ in range(20):
        out = run(source)
        values.add("".join(out).strip())
    assert len(values) > 1, "All 20 RANDOM calls returned the same value"


def test_vm_two_randoms_in_sequence():
    """Two RANDOM ops in sequence push two values."""
    prog = parse("📜 🏠\n  🎲\n  🎲\n  🛑")
    vm = VM(prog)
    vm.run()
    assert len(vm.stack) == 2
    assert all(isinstance(v, float) for v in vm.stack)
    assert all(0.0 <= v < 1.0 for v in vm.stack)


# ── Disassembler ──────────────────────────────────────────────────────────


def test_disasm_random():
    prog = parse("📜 🏠\n  🎲\n  🛑")
    text = disassemble(prog)
    assert "🎲" in text


# ── C AOT compiler ────────────────────────────────────────────────────────


def test_compiler_random_generates_c():
    """RANDOM generates valid C code with rand()/RAND_MAX."""
    prog = parse("📜 🏠\n  🎲\n  🖨️\n  🛑")
    c_code = compile_to_c(prog)
    assert "rand()" in c_code
    assert "RAND_MAX" in c_code
    assert "#include <time.h>" in c_code
    assert "srand(time(NULL))" in c_code


def test_compiler_random_numeric_only():
    """A RANDOM-only program stays on the numeric fast path (no strings)."""
    prog = parse("📜 🏠\n  🎲\n  🖨️\n  🛑")
    c_code = compile_to_c(prog)
    assert "numeric-only fast path" in c_code


def test_compiler_random_compiles():
    """If clang is available, compile and run a RANDOM program."""
    import shutil
    if not shutil.which("clang"):
        import pytest
        pytest.skip("clang not available")

    prog = parse("📜 🏠\n  🎲\n  🖨️\n  🛑")
    c_code = compile_to_c(prog)

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as f:
        f.write(c_code)
        c_path = f.name

    bin_path = c_path[:-2]
    try:
        result = subprocess.run(
            ["clang", "-O2", "-o", bin_path, c_path],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Compile failed: {result.stderr}"

        result = subprocess.run([bin_path], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0
        val = float(result.stdout.strip())
        assert 0.0 <= val <= 1.0
    finally:
        os.unlink(c_path)
        if os.path.exists(bin_path):
            os.unlink(bin_path)


# ── Monte Carlo pi example ───────────────────────────────────────────────


def test_monte_carlo_pi():
    """Monte Carlo pi estimation should produce a result in [2.5, 3.8]."""
    example_path = os.path.join(
        os.path.dirname(__file__), "..", "examples", "monte_carlo_pi.emoji"
    )
    with open(example_path) as f:
        source = f.read()
    out = run(source, max_steps=500_000)
    text = "".join(out).strip()
    val = float(text)
    assert 2.5 <= val <= 3.8, f"Monte Carlo pi = {val}, expected ~3.14"
