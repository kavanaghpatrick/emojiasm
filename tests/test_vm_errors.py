"""Tests for all VMError paths in EmojiASM."""

import pytest
from emojiasm.parser import parse
from emojiasm.vm import VM, VMError


def run(source, max_steps=10000):
    program = parse(source)
    vm = VM(program)
    vm.max_steps = max_steps
    return vm.run()


# ---------------------------------------------------------------------------
# 1. Stack underflow: pop from empty stack
# ---------------------------------------------------------------------------

def test_stack_underflow():
    # POP (📤) on an empty stack should raise VMError with "underflow"
    with pytest.raises(VMError, match="underflow"):
        run("📜 🏠\n  📤\n  🛑")


# ---------------------------------------------------------------------------
# 2. Stack overflow: push beyond stack_size
# ---------------------------------------------------------------------------

def test_stack_overflow():
    # With stack_size=3, pushing a 4th value must raise VMError with "overflow"
    source = "📜 🏠\n  📥 1\n  📥 2\n  📥 3\n  📥 4\n  🛑"
    program = parse(source)
    vm = VM(program, stack_size=3)
    with pytest.raises(VMError, match="overflow"):
        vm.run()


# ---------------------------------------------------------------------------
# 3. OVER with fewer than 2 elements on the stack
# ---------------------------------------------------------------------------

def test_over_underflow():
    # OVER (🫴) needs at least 2 elements; only 1 on stack here
    with pytest.raises(VMError, match="OVER"):
        run("📜 🏠\n  📥 1\n  🫴\n  🛑")


def test_over_empty_stack():
    # OVER on a completely empty stack
    with pytest.raises(VMError, match="OVER"):
        run("📜 🏠\n  🫴\n  🛑")


# ---------------------------------------------------------------------------
# 4. ROT with fewer than 3 elements on the stack
# ---------------------------------------------------------------------------

def test_rot_underflow():
    # ROT (🔄) needs at least 3 elements; only 2 on stack here
    with pytest.raises(VMError, match="ROT"):
        run("📜 🏠\n  📥 1\n  📥 2\n  🔄\n  🛑")


def test_rot_empty_stack():
    # ROT on a completely empty stack
    with pytest.raises(VMError, match="ROT"):
        run("📜 🏠\n  🔄\n  🛑")


# ---------------------------------------------------------------------------
# 5. Division by zero
# ---------------------------------------------------------------------------

def test_div_by_zero():
    with pytest.raises(VMError, match="Division by zero"):
        run("📜 🏠\n  📥 10\n  📥 0\n  ➗\n  🛑")


# ---------------------------------------------------------------------------
# 6. Modulo by zero
# ---------------------------------------------------------------------------

def test_mod_by_zero():
    with pytest.raises(VMError, match="Modulo by zero"):
        run("📜 🏠\n  📥 10\n  📥 0\n  🔢\n  🛑")


# ---------------------------------------------------------------------------
# 7. LOAD on uninitialized memory cell
# ---------------------------------------------------------------------------

def test_load_uninitialized():
    with pytest.raises(VMError, match="not initialized"):
        run("📜 🏠\n  📂 🅰️\n  🛑")


# ---------------------------------------------------------------------------
# 8. JMP to unknown label
# ---------------------------------------------------------------------------

def test_jmp_unknown_label():
    with pytest.raises(VMError, match="Unknown label"):
        run("📜 🏠\n  👉 👻\n  🛑")


# ---------------------------------------------------------------------------
# 9. JZ to unknown label (triggered: push 0, then JZ to nonexistent label)
# ---------------------------------------------------------------------------

def test_jz_unknown_label():
    # val == 0 so the jump is attempted; label does not exist
    with pytest.raises(VMError, match="Unknown label"):
        run("📜 🏠\n  📥 0\n  🤔 👻\n  🛑")


# ---------------------------------------------------------------------------
# 10. JNZ to unknown label (triggered: push 1, then JNZ to nonexistent label)
# ---------------------------------------------------------------------------

def test_jnz_unknown_label():
    # val != 0 so the jump is attempted; label does not exist
    with pytest.raises(VMError, match="Unknown label"):
        run("📜 🏠\n  📥 1\n  😤 👻\n  🛑")


# ---------------------------------------------------------------------------
# 11. CALL to nonexistent function
# ---------------------------------------------------------------------------

def test_call_nonexistent_function():
    with pytest.raises(VMError, match="not found"):
        run("📜 🏠\n  📞 👻\n  🛑")


# ---------------------------------------------------------------------------
# 12. Step limit exceeded (infinite loop with max_steps=10)
# ---------------------------------------------------------------------------

def test_step_limit_exceeded():
    # Unconditional jump back to the same label: infinite loop
    source = "📜 🏠\n🏷️ 🔁\n  👉 🔁\n  🛑"
    with pytest.raises(VMError, match="Execution limit exceeded"):
        run(source, max_steps=10)


# ---------------------------------------------------------------------------
# 13. Entry point not found (manually corrupt program.entry_point)
# ---------------------------------------------------------------------------

def test_entry_point_not_found():
    source = "📜 🏠\n  🛑"
    program = parse(source)
    program.entry_point = "👻"  # point to a function that does not exist
    vm = VM(program)
    with pytest.raises(VMError, match="not found"):
        vm.run()
