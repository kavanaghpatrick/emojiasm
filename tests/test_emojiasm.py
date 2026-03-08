"""Tests for EmojiASM."""

from emojiasm.parser import parse
from emojiasm.vm import VM


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
