"""Stack ops and arithmetic edge case tests for EmojiASM VM.

Covers: OVER, ROT, ADD (string coercion), SUB/MUL/DIV/MOD (floats, floor
division, negative modulo), CMP_LT, CMP_GT, CMP_EQ (strings), NOT (various
truthy/falsy), AND (false branches), OR (false/true branches), DUP (stack
depth), SWAP (order verification).

Intentionally avoids duplicating tests already present in test_emojiasm.py:
  - basic int ADD/SUB/MUL/DIV/MOD
  - DUP used for self-addition
  - SWAP two-print order
  - CMP_EQ with equal/not-equal ints
  - NOT with 0
  - AND with (1, 1)
  - OR with (0, 1)
"""

from emojiasm.parser import parse
from emojiasm.vm import VM


def run(source, max_steps=10000):
    program = parse(source)
    vm = VM(program)
    vm.max_steps = max_steps
    return vm.run()


def run_vm(source):
    """Return the VM object after running, so callers can inspect .stack."""
    program = parse(source)
    vm = VM(program)
    vm.max_steps = 10000
    vm.run()
    return vm


# ---------------------------------------------------------------------------
# OVER  —  [a, b] -> [a, b, a]
# ---------------------------------------------------------------------------

def test_over_pushes_second_from_top():
    """OVER copies the second-from-top element: push 10, push 20, OVER -> top is 10."""
    # Stack after OVER: [10, 20, 10] — print top (10), then print next (20).
    out = run("📜 🏠\n  📥 10\n  📥 20\n  🫴\n  🖨️\n  🖨️\n  🛑")
    lines = "".join(out).strip().split("\n")
    assert lines[0] == "10", f"Expected top=10 after OVER, got {lines[0]}"
    assert lines[1] == "20", f"Expected second=20 after OVER, got {lines[1]}"


def test_over_leaves_original_intact():
    """OVER must not consume the original elements — stack depth grows by 1."""
    vm = run_vm("📜 🏠\n  📥 10\n  📥 20\n  🫴\n  🛑")
    assert vm.stack == [10, 20, 10], f"Expected [10, 20, 10], got {vm.stack}"


# ---------------------------------------------------------------------------
# ROT  —  [a, b, c] -> [b, c, a]
# ---------------------------------------------------------------------------

def test_rot_moves_third_to_top():
    """ROT rotates: push 1, push 2, push 3 -> [1, 2, 3]; ROT -> [2, 3, 1], top=1."""
    out = run("📜 🏠\n  📥 1\n  📥 2\n  📥 3\n  🔄\n  🖨️\n  🛑")
    assert "".join(out).strip() == "1", "ROT should bring bottom element to top"


def test_rot_full_stack_order():
    """ROT: [1, 2, 3] -> [2, 3, 1] — verify complete resulting stack."""
    vm = run_vm("📜 🏠\n  📥 1\n  📥 2\n  📥 3\n  🔄\n  🛑")
    assert vm.stack == [2, 3, 1], f"Expected [2, 3, 1] after ROT, got {vm.stack}"


# ---------------------------------------------------------------------------
# ADD — string concatenation and int/string coercion
# ---------------------------------------------------------------------------

def test_add_two_strings():
    """ADD concatenates two strings: 'hello' + ' world' = 'hello world'."""
    out = run('📜 🏠\n  📥 "hello"\n  📥 " world"\n  ➕\n  🖨️\n  🛑')
    assert "".join(out).strip() == "hello world"


def test_add_int_plus_string_coerces():
    """ADD with int on bottom, string on top: 42 + '!' = '42!'."""
    out = run('📜 🏠\n  📥 42\n  📥 "!"\n  ➕\n  🖨️\n  🛑')
    assert "".join(out).strip() == "42!"


def test_add_string_plus_int_coerces():
    """ADD with string on bottom, int on top: '!' + 42 = '!42'."""
    out = run('📜 🏠\n  📥 "!"\n  📥 42\n  ➕\n  🖨️\n  🛑')
    assert "".join(out).strip() == "!42"


# ---------------------------------------------------------------------------
# SUB — floats
# ---------------------------------------------------------------------------

def test_sub_floats():
    """SUB with floats: 3.5 - 1.5 = 2.0."""
    out = run("📜 🏠\n  📥 3.5\n  📥 1.5\n  ➖\n  🖨️\n  🛑")
    assert float("".join(out).strip()) == 2.0


# ---------------------------------------------------------------------------
# MUL — floats
# ---------------------------------------------------------------------------

def test_mul_floats():
    """MUL with floats: 2.5 * 4.0 = 10.0."""
    out = run("📜 🏠\n  📥 2.5\n  📥 4.0\n  ✖️\n  🖨️\n  🛑")
    assert float("".join(out).strip()) == 10.0


# ---------------------------------------------------------------------------
# DIV — floor division (int/int), float division
# ---------------------------------------------------------------------------

def test_div_int_floor():
    """DIV with int/int uses floor division: 7 / 2 = 3."""
    out = run("📜 🏠\n  📥 7\n  📥 2\n  ➗\n  🖨️\n  🛑")
    assert "".join(out).strip() == "3"


def test_div_float_numerator():
    """DIV with float numerator: 7.0 / 2 = 3.5."""
    out = run("📜 🏠\n  📥 7.0\n  📥 2\n  ➗\n  🖨️\n  🛑")
    assert float("".join(out).strip()) == 3.5


def test_div_float_denominator():
    """DIV with float denominator: 7 / 2.0 = 3.5."""
    out = run("📜 🏠\n  📥 7\n  📥 2.0\n  ➗\n  🖨️\n  🛑")
    assert float("".join(out).strip()) == 3.5


# ---------------------------------------------------------------------------
# MOD — basic and negative operand (Python semantics)
# ---------------------------------------------------------------------------

def test_mod_basic():
    """MOD: 17 % 5 = 2."""
    out = run("📜 🏠\n  📥 17\n  📥 5\n  🔢\n  🖨️\n  🛑")
    assert "".join(out).strip() == "2"


def test_mod_negative_dividend():
    """MOD with negative dividend follows Python semantics: -1 % 5 = 4."""
    out = run("📜 🏠\n  📥 -1\n  📥 5\n  🔢\n  🖨️\n  🛑")
    assert "".join(out).strip() == "4"


# ---------------------------------------------------------------------------
# CMP_EQ — string comparison
# ---------------------------------------------------------------------------

def test_cmp_eq_strings_equal():
    """CMP_EQ: 'abc' == 'abc' -> 1."""
    out = run('📜 🏠\n  📥 "abc"\n  📥 "abc"\n  🟰\n  🖨️\n  🛑')
    assert "".join(out).strip() == "1"


def test_cmp_eq_strings_not_equal():
    """CMP_EQ: 'abc' == 'xyz' -> 0."""
    out = run('📜 🏠\n  📥 "abc"\n  📥 "xyz"\n  🟰\n  🖨️\n  🛑')
    assert "".join(out).strip() == "0"


# ---------------------------------------------------------------------------
# CMP_LT
# ---------------------------------------------------------------------------

def test_cmp_lt_true():
    """CMP_LT: 3 < 5 -> 1."""
    out = run("📜 🏠\n  📥 3\n  📥 5\n  📏\n  🖨️\n  🛑")
    assert "".join(out).strip() == "1"


def test_cmp_lt_false():
    """CMP_LT: 5 < 3 -> 0."""
    out = run("📜 🏠\n  📥 5\n  📥 3\n  📏\n  🖨️\n  🛑")
    assert "".join(out).strip() == "0"


# ---------------------------------------------------------------------------
# CMP_GT
# ---------------------------------------------------------------------------

def test_cmp_gt_true():
    """CMP_GT: 5 > 3 -> 1."""
    out = run("📜 🏠\n  📥 5\n  📥 3\n  📐\n  🖨️\n  🛑")
    assert "".join(out).strip() == "1"


def test_cmp_gt_false():
    """CMP_GT: 3 > 5 -> 0."""
    out = run("📜 🏠\n  📥 3\n  📥 5\n  📐\n  🖨️\n  🛑")
    assert "".join(out).strip() == "0"


# ---------------------------------------------------------------------------
# NOT — multiple truthy/falsy values
# ---------------------------------------------------------------------------

def test_not_one_gives_zero():
    """NOT 1 -> 0."""
    out = run("📜 🏠\n  📥 1\n  🚫\n  🖨️\n  🛑")
    assert "".join(out).strip() == "0"


def test_not_nonzero_gives_zero():
    """NOT 42 -> 0 (any non-zero int is truthy)."""
    out = run("📜 🏠\n  📥 42\n  🚫\n  🖨️\n  🛑")
    assert "".join(out).strip() == "0"


def test_not_empty_string_gives_one():
    """NOT '' -> 1 (empty string is falsy)."""
    out = run('📜 🏠\n  📥 ""\n  🚫\n  🖨️\n  🛑')
    assert "".join(out).strip() == "1"


# ---------------------------------------------------------------------------
# AND — false branches
# ---------------------------------------------------------------------------

def test_and_false_true():
    """AND: 0 AND 1 -> 0."""
    out = run("📜 🏠\n  📥 0\n  📥 1\n  🤝\n  🖨️\n  🛑")
    assert "".join(out).strip() == "0"


def test_and_true_false():
    """AND: 1 AND 0 -> 0."""
    out = run("📜 🏠\n  📥 1\n  📥 0\n  🤝\n  🖨️\n  🛑")
    assert "".join(out).strip() == "0"


# ---------------------------------------------------------------------------
# OR — false/false and true branches
# ---------------------------------------------------------------------------

def test_or_false_false():
    """OR: 0 OR 0 -> 0."""
    out = run("📜 🏠\n  📥 0\n  📥 0\n  🤙\n  🖨️\n  🛑")
    assert "".join(out).strip() == "0"


def test_or_true_false():
    """OR: 1 OR 0 -> 1."""
    out = run("📜 🏠\n  📥 1\n  📥 0\n  🤙\n  🖨️\n  🛑")
    assert "".join(out).strip() == "1"


def test_or_false_true():
    """OR: 0 OR 1 -> 1."""
    out = run("📜 🏠\n  📥 0\n  📥 1\n  🤙\n  🖨️\n  🛑")
    assert "".join(out).strip() == "1"


# ---------------------------------------------------------------------------
# DUP — stack depth and value identity
# ---------------------------------------------------------------------------

def test_dup_stack_has_two_copies():
    """DUP leaves two copies of the value on the stack."""
    vm = run_vm("📜 🏠\n  📥 77\n  📋\n  🛑")
    assert vm.stack == [77, 77], f"Expected [77, 77] after DUP, got {vm.stack}"


def test_dup_printing_twice_gives_same_value():
    """Printing the two copies produced by DUP yields the same value twice."""
    out = run("📜 🏠\n  📥 77\n  📋\n  🖨️\n  🖨️\n  🛑")
    lines = "".join(out).strip().split("\n")
    assert lines == ["77", "77"], f"Expected ['77', '77'], got {lines}"


# ---------------------------------------------------------------------------
# SWAP — order after swap
# ---------------------------------------------------------------------------

def test_swap_reverses_top_two():
    """SWAP: push 'a', push 'b' -> stack is [b, a] -> pop order is a, b."""
    vm = run_vm('📜 🏠\n  📥 "a"\n  📥 "b"\n  🔀\n  🛑')
    assert vm.stack == ["b", "a"], f"Expected ['b', 'a'] after SWAP, got {vm.stack}"


def test_swap_print_order():
    """After SWAP, printing yields the originally-bottom value first."""
    out = run('📜 🏠\n  📥 "first"\n  📥 "second"\n  🔀\n  🖨️\n  🖨️\n  🛑')
    lines = "".join(out).strip().split("\n")
    assert lines[0] == "first", f"Expected 'first' on top after SWAP, got {lines[0]}"
    assert lines[1] == "second", f"Expected 'second' next, got {lines[1]}"
