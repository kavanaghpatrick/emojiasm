"""Tests for control flow and I/O operations in EmojiASM.

Coverage targets (not already in test_emojiasm.py or test_vm_errors.py):
  - JZ not-taken, JNZ not-taken, condition consumption after JZ
  - HALT termination guard
  - RET at top level, implicit fall-off-end return
  - CALL+RET with return value, nested CALL chain
  - PRINTS (push string, no output)
  - PRINT vs PRINTLN newline distinction
  - NOP (unique fixture: no side-effects beyond continuing)
  - Multiple return values staying on stack after CALL
  - STORE/LOAD round-trip, STORE overwrite, memory global across functions
  - INPUT and INPUT_NUM with mocked stdin
"""

import pytest
from unittest.mock import patch
from emojiasm.parser import parse
from emojiasm.vm import VM, VMError


def run(source, max_steps=10000):
    program = parse(source)
    vm = VM(program)
    vm.max_steps = max_steps
    return vm.run()


def run_vm(source, max_steps=10000):
    """Return (output_buffer, vm) so tests can inspect vm state."""
    program = parse(source)
    vm = VM(program)
    vm.max_steps = max_steps
    out = vm.run()
    return out, vm


# ---------------------------------------------------------------------------
# 1. JZ: non-zero value -> does NOT jump
# ---------------------------------------------------------------------------

def test_jz_not_taken_on_nonzero():
    # Push 5 (non-zero), JZ to skip, fall through to PRINTLN the "1" branch.
    # If JZ incorrectly jumps, "2" is printed instead.
    src = """
📜 🏠
  📥 5
  🤔 🏁
  📥 1
  🖨️
  🛑
🏷️ 🏁
  📥 2
  🖨️
  🛑
"""
    out = run(src)
    assert "".join(out).strip() == "1"


# ---------------------------------------------------------------------------
# 2. JZ: zero value -> DOES jump
# ---------------------------------------------------------------------------

def test_jz_taken_on_zero():
    # Confirmed by test_jump_if_zero in test_emojiasm.py, but tested here with
    # a different value path to keep the fixture self-contained.
    src = """
📜 🏠
  📥 0
  🤔 🏁
  📥 99
  🖨️
  🛑
🏷️ 🏁
  📥 0
  🖨️
  🛑
"""
    out = run(src)
    assert "".join(out).strip() == "0"


# ---------------------------------------------------------------------------
# 3. JNZ: zero value -> does NOT jump
# ---------------------------------------------------------------------------

def test_jnz_not_taken_on_zero():
    src = """
📜 🏠
  📥 0
  😤 🏁
  📥 1
  🖨️
  🛑
🏷️ 🏁
  📥 2
  🖨️
  🛑
"""
    out = run(src)
    assert "".join(out).strip() == "1"


# ---------------------------------------------------------------------------
# 4. JNZ: non-zero value -> DOES jump
# ---------------------------------------------------------------------------

def test_jnz_taken_on_nonzero():
    src = """
📜 🏠
  📥 7
  😤 🏁
  📥 10
  🖨️
  🛑
🏷️ 🏁
  📥 20
  🖨️
  🛑
"""
    out = run(src)
    assert "".join(out).strip() == "20"


# ---------------------------------------------------------------------------
# 5. JZ consumes condition: after JZ (not taken), condition value is gone
# ---------------------------------------------------------------------------

def test_jz_consumes_condition_value():
    # Push 5, then 3. JZ on 3 (non-zero) does not jump.
    # After JZ the stack should have only [5] left (3 was consumed).
    # PRINTLN prints 5.
    src = """
📜 🏠
  📥 5
  📥 3
  🤔 🏁
  🖨️
  🛑
🏷️ 🏁
  📥 99
  🖨️
  🛑
"""
    out = run(src)
    assert "".join(out).strip() == "5"


# ---------------------------------------------------------------------------
# 6. HALT stops execution: instructions after HALT are not reached
# ---------------------------------------------------------------------------

def test_halt_stops_execution():
    # PRINTLN after HALT must never execute; output_buffer stays empty.
    src = """
📜 🏠
  🛑
  📥 42
  🖨️
"""
    out, vm = run_vm(src)
    assert out == []
    assert vm.halted is True


# ---------------------------------------------------------------------------
# 7. RET at top level: function with only RET does not crash
# ---------------------------------------------------------------------------

def test_ret_at_top_level_does_not_crash():
    # RET from the entry function with an empty call_stack simply ends.
    src = """
📜 🏠
  📲
"""
    out = run(src)
    assert out == []


# ---------------------------------------------------------------------------
# 8. Implicit return (fall off end): callee with no RET returns to caller
# ---------------------------------------------------------------------------

def test_implicit_return_fall_off_end():
    # double_push pushes two values but has no RET or HALT.
    # After it falls off the end it should return to main, which prints both.
    src = """
📜 🏠
  📞 🔲
  🖨️
  🖨️
  🛑

📜 🔲
  📥 10
  📥 20
"""
    out = run(src)
    assert "".join(out).strip() == "20\n10"


# ---------------------------------------------------------------------------
# 9. CALL + RET with return value: callee leaves value on stack for caller
# ---------------------------------------------------------------------------

def test_call_ret_with_return_value():
    # square(n): pushes n*n and returns.
    src = """
📜 🏠
  📥 6
  📞 🔲
  🖨️
  🛑

📜 🔲
  📋
  ✖️
  📲
"""
    out = run(src)
    assert "".join(out).strip() == "36"


# ---------------------------------------------------------------------------
# 10. Nested CALL: main -> f -> g -> h, all return correctly
# ---------------------------------------------------------------------------

def test_nested_call_chain():
    # h adds 1, g doubles, f squares; main pushes 3, calls f, prints result.
    # h(x) = x+1  ->  g(x) = 2*x  ->  f(x) = x*x
    # main: push 3, call f  -> f: call g -> g: call h -> h: 3+1=4, ret
    #   -> g: 4*2=8, ret -> f: 8*8=64, ret -> main: print 64
    src = """
📜 🏠
  📥 3
  📞 🅵
  🖨️
  🛑

📜 🅵
  📞 🅶
  📋
  ✖️
  📲

📜 🅶
  📞 🅷
  📥 2
  ✖️
  📲

📜 🅷
  📥 1
  ➕
  📲
"""
    out = run(src)
    assert "".join(out).strip() == "64"


# ---------------------------------------------------------------------------
# 11. PRINTS: pushes string WITHOUT printing (output_buffer stays empty)
# ---------------------------------------------------------------------------

def test_prints_does_not_produce_output():
    # 💬 "hello" pushes the string; we intentionally do NOT follow it with
    # PRINT or PRINTLN, so output_buffer must remain empty.
    src = """
📜 🏠
  💬 "hello"
  🛑
"""
    out, vm = run_vm(src)
    assert out == []
    # The string is on the stack
    assert vm.stack == ["hello"]


# ---------------------------------------------------------------------------
# 12. PRINT vs PRINTLN newline distinction
# ---------------------------------------------------------------------------

def test_print_no_newline():
    # 📢 appends the bare value with no trailing newline.
    src = """
📜 🏠
  💬 "hi"
  📢
  🛑
"""
    out = run(src)
    assert out == ["hi"]          # no \n appended


def test_println_adds_newline():
    # 🖨️ appends the value with a trailing newline.
    src = """
📜 🏠
  💬 "hi"
  🖨️
  🛑
"""
    out = run(src)
    assert out == ["hi\n"]        # \n is appended


# ---------------------------------------------------------------------------
# 13. NOP: does nothing, execution continues normally
# ---------------------------------------------------------------------------

def test_nop_does_nothing():
    # Three NOPs between PUSH and PRINTLN; value must survive unchanged.
    src = """
📜 🏠
  📥 7
  💤
  💤
  💤
  🖨️
  🛑
"""
    out, vm = run_vm(src)
    assert "".join(out).strip() == "7"
    assert vm.stack == []         # value was consumed by PRINTLN


# ---------------------------------------------------------------------------
# 14. Multiple return values stay on stack after CALL
# ---------------------------------------------------------------------------

def test_multiple_return_values_on_stack():
    # push_pair pushes 10 and 20; caller prints both.
    src = """
📜 🏠
  📞 🔲
  🖨️
  🖨️
  🛑

📜 🔲
  📥 10
  📥 20
  📲
"""
    out = run(src)
    assert "".join(out).strip() == "20\n10"


# ---------------------------------------------------------------------------
# 15. STORE/LOAD: store a value, load it back, it is the same
# ---------------------------------------------------------------------------

def test_store_load_round_trip():
    src = """
📜 🏠
  📥 123
  💾 🅰️
  📂 🅰️
  🖨️
  🛑
"""
    out = run(src)
    assert "".join(out).strip() == "123"


# ---------------------------------------------------------------------------
# 16. STORE overwrites: second store wins
# ---------------------------------------------------------------------------

def test_store_overwrites_previous_value():
    src = """
📜 🏠
  📥 1
  💾 🅰️
  📥 2
  💾 🅰️
  📂 🅰️
  🖨️
  🛑
"""
    out = run(src)
    assert "".join(out).strip() == "2"


# ---------------------------------------------------------------------------
# 17. Memory is global across functions: store in one, load in another
# ---------------------------------------------------------------------------

def test_memory_shared_across_functions():
    # main stores 77 in cell 🅱️, then calls reader which loads and prints it.
    src = """
📜 🏠
  📥 77
  💾 🅱️
  📞 🔲
  🛑

📜 🔲
  📂 🅱️
  🖨️
  📲
"""
    out = run(src)
    assert "".join(out).strip() == "77"


# ---------------------------------------------------------------------------
# 18. INPUT: mocked stdin returns a string that lands on the stack
# ---------------------------------------------------------------------------

def test_input_pushes_string():
    src = """
📜 🏠
  🎤
  🖨️
  🛑
"""
    with patch("builtins.input", return_value="hello world"):
        out = run(src)
    assert "".join(out).strip() == "hello world"


# ---------------------------------------------------------------------------
# 19. INPUT_NUM: mocked stdin returns "42", VM pushes integer 42
# ---------------------------------------------------------------------------

def test_input_num_pushes_integer():
    src = """
📜 🏠
  🔟
  📥 8
  ➕
  🖨️
  🛑
"""
    with patch("builtins.input", return_value="42"):
        out = run(src)
    # 42 + 8 = 50, confirming INPUT_NUM pushed an integer (not a string)
    assert "".join(out).strip() == "50"


# ---------------------------------------------------------------------------
# 20. INPUT_NUM: non-numeric input raises VMError
# ---------------------------------------------------------------------------

def test_input_num_non_numeric_raises_vmerror():
    src = """
📜 🏠
  🔟
  🖨️
  🛑
"""
    with patch("builtins.input", return_value="not-a-number"):
        with pytest.raises(VMError, match="Invalid numeric input"):
            run(src)
