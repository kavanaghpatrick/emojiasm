"""Tests for EmojiASM."""

import pytest

from emojiasm.parser import parse
from emojiasm.vm import VM, VMError


def run(source: str, max_steps: int = 10000) -> list[str]:
    program = parse(source)
    vm = VM(program)
    vm.max_steps = max_steps
    return vm.run()


def test_hello():
    out = run('📜 🏠\n  💬 "Hello"\n  📢\n  🛑')
    assert "".join(out) == "Hello"


def test_addition():
    out = run("📜 🏠\n  📥 3\n  📥 4\n  ➕\n  🖨️\n  🛑")
    assert "".join(out).strip() == "7"


def test_subtraction():
    out = run("📜 🏠\n  📥 10\n  📥 3\n  ➖\n  🖨️\n  🛑")
    assert "".join(out).strip() == "7"


def test_multiplication():
    out = run("📜 🏠\n  📥 6\n  📥 7\n  ✖️\n  🖨️\n  🛑")
    assert "".join(out).strip() == "42"


def test_division():
    out = run("📜 🏠\n  📥 20\n  📥 4\n  ➗\n  🖨️\n  🛑")
    assert "".join(out).strip() == "5"


def test_modulo():
    out = run("📜 🏠\n  📥 17\n  📥 5\n  🔢\n  🖨️\n  🛑")
    assert "".join(out).strip() == "2"


def test_dup():
    out = run("📜 🏠\n  📥 42\n  📋\n  ➕\n  🖨️\n  🛑")
    assert "".join(out).strip() == "84"


def test_swap():
    out = run("📜 🏠\n  📥 1\n  📥 2\n  🔀\n  🖨️\n  🖨️\n  🛑")
    assert "".join(out).strip() == "1\n2"


def test_store_load():
    out = run("📜 🏠\n  📥 99\n  💾 🅰️\n  📂 🅰️\n  🖨️\n  🛑")
    assert "".join(out).strip() == "99"


def test_jump():
    out = run("📜 🏠\n  👉 🏁\n  📥 1\n  🖨️\n🏷️ 🏁\n  📥 2\n  🖨️\n  🛑")
    assert "".join(out).strip() == "2"


def test_jump_if_zero():
    out = run("📜 🏠\n  📥 0\n  🤔 🏁\n  📥 1\n  🖨️\n  🛑\n🏷️ 🏁\n  📥 2\n  🖨️\n  🛑")
    assert "".join(out).strip() == "2"


def test_jump_if_not_zero():
    out = run("📜 🏠\n  📥 1\n  😤 🏁\n  📥 10\n  🖨️\n  🛑\n🏷️ 🏁\n  📥 20\n  🖨️\n  🛑")
    assert "".join(out).strip() == "20"


def test_compare_equal():
    out = run("📜 🏠\n  📥 5\n  📥 5\n  🟰\n  🖨️\n  🛑")
    assert "".join(out).strip() == "1"


def test_compare_not_equal():
    out = run("📜 🏠\n  📥 5\n  📥 3\n  🟰\n  🖨️\n  🛑")
    assert "".join(out).strip() == "0"


def test_function_call():
    source = "📜 🏠\n  📥 5\n  📞 🔲\n  🖨️\n  🛑\n📜 🔲\n  📋\n  ✖️\n  📲"
    out = run(source)
    assert "".join(out).strip() == "25"


def test_loop_counter():
    source = """
📜 🏠
  📥 0
  💾 🔢
🏷️ 🔁
  📂 🔢
  📥 5
  🟰
  😤 🏁
  📂 🔢
  📥 1
  ➕
  💾 🔢
  👉 🔁
🏷️ 🏁
  📂 🔢
  🖨️
  🛑
"""
    out = run(source)
    assert "".join(out).strip() == "5"


def test_string_concat():
    out = run('📜 🏠\n  📥 10\n  📥 20\n  ➕\n  💬 " = thirty"\n  ➕\n  🖨️\n  🛑')
    assert "".join(out).strip() == "30 = thirty"


def test_not():
    out = run("📜 🏠\n  📥 0\n  🚫\n  🖨️\n  🛑")
    assert "".join(out).strip() == "1"


def test_logical_and():
    out = run("📜 🏠\n  📥 1\n  📥 1\n  🤝\n  🖨️\n  🛑")
    assert "".join(out).strip() == "1"


def test_logical_or():
    out = run("📜 🏠\n  📥 0\n  📥 1\n  🤙\n  🖨️\n  🛑")
    assert "".join(out).strip() == "1"


def test_nop():
    out = run("📜 🏠\n  📥 42\n  💤\n  💤\n  💤\n  🖨️\n  🛑")
    assert "".join(out).strip() == "42"


def test_deep_recursion_no_stack_overflow():
    """Iterative dispatch must handle >1000 nested calls without RecursionError."""
    # countdown(n): if n==0 return 0; else return countdown(n-1)
    # 1200 nested calls exceeds CPython's default 1000-frame recursion limit.
    src = "\n".join([
        "📜 🏠",
        "  📥 1200",
        "  📞 🔽",
        "  🖨️",
        "  🛑",
        "",
        "📜 🔽",
        "  📋",          # DUP n          → [n, n]
        "  📥 0",
        "  🟰",          # n == 0?        → [n, bool]
        "  🤔 🔁",       # JZ 🔁: jump to recurse if bool==0 (n != 0)
        "  📲",          # n == 0: return n (which is 0) ✓
        "  🏷️ 🔁",
        "  📥 1",
        "  ➖",          # n - 1
        "  📞 🔽",       # countdown(n-1), result on stack
        "  📲",
    ])
    out = run(src, max_steps=5_000_000)
    assert "".join(out).strip() == "0"


# --- Math opcodes (Tier 1) ---


def test_pow():
    out = run("📥 2\n📥 10\n🔋\n🖨️\n🛑")
    assert "".join(out).strip() == "1024"


def test_pow_negative_exponent():
    out = run("📥 2\n📥 -1\n🔋\n🖨️\n🛑")
    assert "".join(out).strip() == "0.5"


def test_sqrt():
    out = run("📥 16\n🌱\n🖨️\n🛑")
    assert "".join(out).strip() == "4.0"


def test_sqrt_float():
    out = run("📥 2\n🌱\n🖨️\n🛑")
    val = float("".join(out).strip())
    assert abs(val - 1.4142135623730951) < 1e-6


def test_sin():
    out = run("📥 0\n📈\n🖨️\n🛑")
    assert "".join(out).strip() == "0.0"


def test_cos():
    out = run("📥 0\n📉\n🖨️\n🛑")
    assert "".join(out).strip() == "1.0"


def test_exp():
    out = run("📥 0\n🚀\n🖨️\n🛑")
    assert "".join(out).strip() == "1.0"


def test_log():
    out = run("📥 1\n📓\n🖨️\n🛑")
    assert "".join(out).strip() == "0.0"


def test_abs_int():
    out = run("📥 -5\n💪\n🖨️\n🛑")
    assert "".join(out).strip() == "5"


def test_abs_float():
    out = run("📥 -3.14\n💪\n🖨️\n🛑")
    assert "".join(out).strip() == "3.14"


def test_min():
    out = run("📥 3\n📥 7\n⬇️\n🖨️\n🛑")
    assert "".join(out).strip() == "3"


def test_max():
    out = run("📥 3\n📥 7\n⬆️\n🖨️\n🛑")
    assert "".join(out).strip() == "7"


# --- Array opcodes ---


def test_array_alloc_and_store():
    """Allocate array of 3, store 42 at index 0, load and print it."""
    out = run("📜 🏠\n  📥 3\n  🗃️ 🅰️\n  📥 0\n  📥 42\n  ✏️ 🅰️\n  📥 0\n  📖 🅰️\n  🖨️\n  🛑")
    assert "".join(out).strip() == "42"


def test_array_load():
    """Allocate array, store values at indices 0, 1, 2, load each and verify."""
    src = "\n".join([
        "📜 🏠",
        "  📥 3",
        "  🗃️ 🅰️",
        "  📥 0",
        "  📥 10",
        "  ✏️ 🅰️",
        "  📥 1",
        "  📥 20",
        "  ✏️ 🅰️",
        "  📥 2",
        "  📥 30",
        "  ✏️ 🅰️",
        "  📥 0",
        "  📖 🅰️",
        "  🖨️",
        "  📥 1",
        "  📖 🅰️",
        "  🖨️",
        "  📥 2",
        "  📖 🅰️",
        "  🖨️",
        "  🛑",
    ])
    out = run(src)
    assert "".join(out).strip() == "10\n20\n30"


def test_array_len():
    """Allocate array of 5, use ALEN to get length, verify it's 5."""
    out = run("📜 🏠\n  📥 5\n  🗃️ 🅰️\n  🧮 🅰️\n  🖨️\n  🛑")
    assert "".join(out).strip() == "5"


def test_array_bounds_error():
    """Access index out of bounds raises VMError."""
    with pytest.raises(VMError):
        run("📜 🏠\n  📥 3\n  🗃️ 🅰️\n  📥 5\n  📖 🅰️\n  🛑")


def test_array_non_array_error():
    """ALOAD on a scalar cell raises VMError."""
    with pytest.raises(VMError):
        run("📜 🏠\n  📥 42\n  💾 🅰️\n  📥 0\n  📖 🅰️\n  🛑")


# --- Comprehensive array tests ---


def test_array_multi_element():
    """Allocate array of 10, store values at multiple indices, verify each."""
    src = "\n".join([
        "📜 🏠",
        "  📥 10",
        "  🗃️ 🅰️",
        # Store i*10 at each index 0-9
        "  📥 0\n  📥 0\n  ✏️ 🅰️",
        "  📥 1\n  📥 10\n  ✏️ 🅰️",
        "  📥 2\n  📥 20\n  ✏️ 🅰️",
        "  📥 3\n  📥 30\n  ✏️ 🅰️",
        "  📥 4\n  📥 40\n  ✏️ 🅰️",
        "  📥 5\n  📥 50\n  ✏️ 🅰️",
        "  📥 6\n  📥 60\n  ✏️ 🅰️",
        "  📥 7\n  📥 70\n  ✏️ 🅰️",
        "  📥 8\n  📥 80\n  ✏️ 🅰️",
        "  📥 9\n  📥 90\n  ✏️ 🅰️",
        # Load and print each
        "  📥 0\n  📖 🅰️\n  🖨️",
        "  📥 4\n  📖 🅰️\n  🖨️",
        "  📥 9\n  📖 🅰️\n  🖨️",
        "  🛑",
    ])
    out = run(src)
    assert "".join(out).strip() == "0\n40\n90"


def test_array_store_load_roundtrip():
    """Store value, load it back, verify it matches."""
    src = "\n".join([
        "📜 🏠",
        "  📥 1",
        "  🗃️ 🅰️",
        "  📥 0",
        "  📥 12345",
        "  ✏️ 🅰️",
        "  📥 0",
        "  📖 🅰️",
        "  🖨️",
        "  🛑",
    ])
    out = run(src)
    assert "".join(out).strip() == "12345"


def test_array_alen_various_sizes():
    """Verify ALEN returns correct length for various sizes."""
    for size in [1, 3, 7, 10, 100]:
        src = f"📜 🏠\n  📥 {size}\n  🗃️ 🅰️\n  🧮 🅰️\n  🖨️\n  🛑"
        out = run(src)
        assert "".join(out).strip() == str(size), f"ALEN failed for size {size}"


def test_array_alen_zero():
    """ALEN of empty array (size 0) returns 0."""
    out = run("📜 🏠\n  📥 0\n  🗃️ 🅰️\n  🧮 🅰️\n  🖨️\n  🛑")
    assert "".join(out).strip() == "0"


def test_array_overwrite_element():
    """Store a value, then overwrite it, verify new value."""
    src = "\n".join([
        "📜 🏠",
        "  📥 3",
        "  🗃️ 🅰️",
        "  📥 1",
        "  📥 42",
        "  ✏️ 🅰️",
        # Overwrite index 1 with 99
        "  📥 1",
        "  📥 99",
        "  ✏️ 🅰️",
        "  📥 1",
        "  📖 🅰️",
        "  🖨️",
        "  🛑",
    ])
    out = run(src)
    assert "".join(out).strip() == "99"


def test_array_multiple_arrays():
    """Use 2 arrays simultaneously, verify independent storage."""
    src = "\n".join([
        "📜 🏠",
        "  📥 3",
        "  🗃️ 🅰️",
        "  📥 3",
        "  🗃️ 🅱️",
        # Store in array A
        "  📥 0",
        "  📥 10",
        "  ✏️ 🅰️",
        "  📥 1",
        "  📥 20",
        "  ✏️ 🅰️",
        # Store different values in array B
        "  📥 0",
        "  📥 100",
        "  ✏️ 🅱️",
        "  📥 1",
        "  📥 200",
        "  ✏️ 🅱️",
        # Load from both and print
        "  📥 0",
        "  📖 🅰️",
        "  🖨️",
        "  📥 1",
        "  📖 🅰️",
        "  🖨️",
        "  📥 0",
        "  📖 🅱️",
        "  🖨️",
        "  📥 1",
        "  📖 🅱️",
        "  🖨️",
        "  🛑",
    ])
    out = run(src)
    assert "".join(out).strip() == "10\n20\n100\n200"


def test_array_in_function_call():
    """Array operations across function calls (shared memory)."""
    src = "\n".join([
        "📜 🏠",
        "  📥 3",
        "  🗃️ 🅰️",
        "  📥 0",
        "  📥 42",
        "  ✏️ 🅰️",
        "  📞 🔲",
        "  📥 0",
        "  📖 🅰️",
        "  🖨️",
        "  🛑",
        "",
        "📜 🔲",
        # Function modifies array element
        "  📥 0",
        "  📥 999",
        "  ✏️ 🅰️",
        "  📲",
    ])
    out = run(src)
    assert "".join(out).strip() == "999"


def test_array_with_loop():
    """Loop pattern: for i in range(5): arr[i] = i*i."""
    src = "\n".join([
        "📜 🏠",
        "  📥 5",
        "  🗃️ 🅰️",
        # i = 0
        "  📥 0",
        "  💾 🔢",
        "🏷️ 🔁",
        # if i == 5, jump to end
        "  📂 🔢",
        "  📥 5",
        "  🟰",
        "  😤 🏁",
        # arr[i] = i * i
        "  📂 🔢",       # push index
        "  📂 🔢",       # push i
        "  📂 🔢",       # push i
        "  ✖️",           # i * i
        "  ✏️ 🅰️",       # store at index i
        # i = i + 1
        "  📂 🔢",
        "  📥 1",
        "  ➕",
        "  💾 🔢",
        "  👉 🔁",
        "🏷️ 🏁",
        # Print arr[0] through arr[4]
        "  📥 0\n  📖 🅰️\n  🖨️",
        "  📥 1\n  📖 🅰️\n  🖨️",
        "  📥 2\n  📖 🅰️\n  🖨️",
        "  📥 3\n  📖 🅰️\n  🖨️",
        "  📥 4\n  📖 🅰️\n  🖨️",
        "  🛑",
    ])
    out = run(src)
    assert "".join(out).strip() == "0\n1\n4\n9\n16"


def test_array_negative_alloc_size():
    """Negative alloc size raises VMError."""
    with pytest.raises(VMError):
        run("📜 🏠\n  📥 -1\n  🗃️ 🅰️\n  🛑")


def test_array_out_of_bounds_load():
    """Loading from out-of-bounds index raises VMError."""
    with pytest.raises(VMError):
        run("📜 🏠\n  📥 3\n  🗃️ 🅰️\n  📥 3\n  📖 🅰️\n  🛑")


def test_array_out_of_bounds_store():
    """Storing to out-of-bounds index raises VMError."""
    with pytest.raises(VMError):
        run("📜 🏠\n  📥 3\n  🗃️ 🅰️\n  📥 5\n  📥 42\n  ✏️ 🅰️\n  🛑")


def test_array_negative_index_load():
    """Negative index on ALOAD raises VMError."""
    with pytest.raises(VMError):
        run("📜 🏠\n  📥 3\n  🗃️ 🅰️\n  📥 -1\n  📖 🅰️\n  🛑")


def test_array_negative_index_store():
    """Negative index on ASTORE raises VMError."""
    with pytest.raises(VMError):
        run("📜 🏠\n  📥 3\n  🗃️ 🅰️\n  📥 -1\n  📥 42\n  ✏️ 🅰️\n  🛑")


def test_array_astore_on_scalar():
    """ASTORE on a scalar cell raises VMError."""
    with pytest.raises(VMError):
        run("📜 🏠\n  📥 42\n  💾 🅰️\n  📥 0\n  📥 99\n  ✏️ 🅰️\n  🛑")


def test_array_alen_on_scalar():
    """ALEN on a scalar cell raises VMError."""
    with pytest.raises(VMError):
        run("📜 🏠\n  📥 42\n  💾 🅰️\n  🧮 🅰️\n  🛑")


def test_array_aload_uninitialized():
    """ALOAD on uninitialized cell raises VMError."""
    with pytest.raises(VMError):
        run("📜 🏠\n  📥 0\n  📖 🅱️\n  🛑")
