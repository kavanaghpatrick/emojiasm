"""Tests for the Python-to-EmojiASM transpiler."""

import pytest
from emojiasm.transpiler import (
    transpile, transpile_to_source, TranspileError,
    EMOJI_POOL, FUNC_EMOJI_POOL,
)
from emojiasm.vm import VM


def run_py(source: str) -> str:
    """Transpile Python, run on VM, return output as string."""
    program = transpile(source)
    out = VM(program).run()
    return "".join(out)


# ── Expression compilation ───────────────────────────────────────────────


class TestLiterals:
    def test_integer(self):
        assert run_py("print(42)").strip() == "42"

    def test_negative_integer(self):
        assert run_py("print(-7)").strip() == "-7"

    def test_zero(self):
        assert run_py("print(0)").strip() == "0"

    def test_float(self):
        assert run_py("print(3.14)").strip() == "3.14"

    def test_negative_float(self):
        assert run_py("print(-0.5)").strip() == "-0.5"

    def test_true(self):
        assert run_py("print(True)").strip() == "1"

    def test_false(self):
        assert run_py("print(False)").strip() == "0"


class TestArithmetic:
    def test_add(self):
        assert run_py("print(3 + 4)").strip() == "7"

    def test_sub(self):
        assert run_py("print(10 - 3)").strip() == "7"

    def test_mul(self):
        assert run_py("print(6 * 7)").strip() == "42"

    def test_floor_div(self):
        assert run_py("print(7 // 2)").strip() == "3"

    def test_true_div(self):
        assert run_py("print(7 / 2)").strip() == "3.5"

    def test_mod(self):
        assert run_py("print(10 % 3)").strip() == "1"

    def test_precedence(self):
        assert run_py("print(2 + 3 * 4)").strip() == "14"

    def test_parentheses(self):
        assert run_py("print((2 + 3) * 4)").strip() == "20"

    def test_complex_expr(self):
        assert run_py("print(3 + 4 * 5)").strip() == "23"

    def test_nested_parens(self):
        assert run_py("print((2 + 3) * (4 - 1))").strip() == "15"


class TestUnaryOps:
    def test_neg(self):
        assert run_py("print(-5)").strip() == "-5"

    def test_pos(self):
        assert run_py("print(+5)").strip() == "5"

    def test_not_zero(self):
        assert run_py("print(not 0)").strip() == "1"

    def test_not_nonzero(self):
        assert run_py("print(not 1)").strip() == "0"

    def test_not_true(self):
        assert run_py("print(not True)").strip() == "0"

    def test_double_neg(self):
        assert run_py("print(-(-3))").strip() == "3"


class TestComparisons:
    def test_eq_true(self):
        assert run_py("print(5 == 5)").strip() == "1"

    def test_eq_false(self):
        assert run_py("print(5 == 3)").strip() == "0"

    def test_neq_true(self):
        assert run_py("print(5 != 3)").strip() == "1"

    def test_neq_false(self):
        assert run_py("print(5 != 5)").strip() == "0"

    def test_lt_true(self):
        assert run_py("print(3 < 5)").strip() == "1"

    def test_lt_false(self):
        assert run_py("print(5 < 3)").strip() == "0"

    def test_gt_true(self):
        assert run_py("print(5 > 3)").strip() == "1"

    def test_gt_false(self):
        assert run_py("print(3 > 5)").strip() == "0"

    def test_lte_true(self):
        assert run_py("print(3 <= 5)").strip() == "1"

    def test_lte_equal(self):
        assert run_py("print(5 <= 5)").strip() == "1"

    def test_lte_false(self):
        assert run_py("print(5 <= 3)").strip() == "0"

    def test_gte_true(self):
        assert run_py("print(5 >= 3)").strip() == "1"

    def test_gte_equal(self):
        assert run_py("print(5 >= 5)").strip() == "1"

    def test_gte_false(self):
        assert run_py("print(3 >= 5)").strip() == "0"


class TestBooleanOps:
    def test_and_true(self):
        assert run_py("print(1 and 1)").strip() == "1"

    def test_and_false(self):
        assert run_py("print(1 and 0)").strip() == "0"

    def test_or_true(self):
        assert run_py("print(0 or 1)").strip() == "1"

    def test_or_false(self):
        assert run_py("print(0 or 0)").strip() == "0"

    def test_combined(self):
        assert run_py("print(1 < 2 and 3 > 1)").strip() == "1"

    def test_multi_and(self):
        assert run_py("print(1 and 2 and 3)").strip() == "1"

    def test_multi_or(self):
        assert run_py("print(0 or 0 or 1)").strip() == "1"


# ── Variables and assignment ─────────────────────────────────────────────


class TestVariables:
    def test_simple_assign(self):
        assert run_py("x = 5\nprint(x)").strip() == "5"

    def test_multiple_vars(self):
        assert run_py("x = 3\ny = 4\nprint(x + y)").strip() == "7"

    def test_reassign(self):
        assert run_py("x = 1\nx = 2\nprint(x)").strip() == "2"

    def test_multi_target(self):
        out = run_py("a = b = 5\nprint(a)\nprint(b)")
        lines = out.strip().split("\n")
        assert lines == ["5", "5"]

    def test_augmented_add(self):
        assert run_py("x = 5\nx += 3\nprint(x)").strip() == "8"

    def test_augmented_sub(self):
        assert run_py("x = 10\nx -= 3\nprint(x)").strip() == "7"

    def test_augmented_mul(self):
        assert run_py("x = 5\nx *= 3\nprint(x)").strip() == "15"

    def test_augmented_floordiv(self):
        assert run_py("x = 10\nx //= 3\nprint(x)").strip() == "3"

    def test_augmented_mod(self):
        assert run_py("x = 10\nx %= 3\nprint(x)").strip() == "1"

    def test_augmented_truediv(self):
        assert run_py("x = 7\nx /= 2\nprint(x)").strip() == "3.5"

    def test_var_in_expression(self):
        assert run_py("x = 5\ny = x + 3\nprint(y)").strip() == "8"

    def test_var_comparison(self):
        assert run_py("x = 5\nprint(x == 5)").strip() == "1"


# ── Control flow ─────────────────────────────────────────────────────────


class TestIfStatements:
    def test_if_true(self):
        assert run_py("if True:\n    print(1)").strip() == "1"

    def test_if_false(self):
        assert run_py("if False:\n    print(1)").strip() == ""

    def test_if_else_true(self):
        src = "x = 5\nif x > 3:\n    print(1)\nelse:\n    print(0)"
        assert run_py(src).strip() == "1"

    def test_if_else_false(self):
        src = "x = 1\nif x > 3:\n    print(1)\nelse:\n    print(0)"
        assert run_py(src).strip() == "0"

    def test_elif(self):
        src = "x = 1\nif x > 5:\n    print(1)\nelif x > 0:\n    print(2)\nelse:\n    print(3)"
        assert run_py(src).strip() == "2"

    def test_elif_last_branch(self):
        src = "x = -1\nif x > 5:\n    print(1)\nelif x > 0:\n    print(2)\nelse:\n    print(3)"
        assert run_py(src).strip() == "3"

    def test_nested_if(self):
        src = "x = 5\nif x > 0:\n    if x > 3:\n        print(1)\n    else:\n        print(2)"
        assert run_py(src).strip() == "1"

    def test_ternary(self):
        src = "x = 5\ny = 1 if x > 3 else 0\nprint(y)"
        assert run_py(src).strip() == "1"


class TestWhileLoop:
    def test_counter(self):
        src = "i = 0\nwhile i < 5:\n    i += 1\nprint(i)"
        assert run_py(src).strip() == "5"

    def test_accumulator(self):
        src = "s = 0\ni = 1\nwhile i <= 10:\n    s += i\n    i += 1\nprint(s)"
        assert run_py(src).strip() == "55"

    def test_break(self):
        src = "i = 0\nwhile True:\n    if i >= 3:\n        break\n    i += 1\nprint(i)"
        assert run_py(src).strip() == "3"

    def test_continue(self):
        src = "s = 0\ni = 0\nwhile i < 5:\n    i += 1\n    if i == 3:\n        continue\n    s += i\nprint(s)"
        assert run_py(src).strip() == "12"


class TestForLoop:
    def test_range_1arg(self):
        src = "s = 0\nfor i in range(5):\n    s += i\nprint(s)"
        assert run_py(src).strip() == "10"

    def test_range_2args(self):
        src = "s = 0\nfor i in range(2, 5):\n    s += i\nprint(s)"
        assert run_py(src).strip() == "9"

    def test_range_3args(self):
        src = "s = 0\nfor i in range(0, 10, 2):\n    s += i\nprint(s)"
        assert run_py(src).strip() == "20"

    def test_nested_for(self):
        src = "s = 0\nfor i in range(3):\n    for j in range(3):\n        s += 1\nprint(s)"
        assert run_py(src).strip() == "9"

    def test_break_in_for(self):
        src = "s = 0\nfor i in range(10):\n    if i == 5:\n        break\n    s += i\nprint(s)"
        assert run_py(src).strip() == "10"

    def test_for_with_conditional(self):
        src = "s = 0\nfor i in range(10):\n    if i % 2 == 0:\n        s += i\nprint(s)"
        assert run_py(src).strip() == "20"


# ── Functions and random ─────────────────────────────────────────────────


class TestFunctions:
    def test_simple_function(self):
        src = "def square(x):\n    return x * x\nprint(square(7))"
        assert run_py(src).strip() == "49"

    def test_two_params(self):
        src = "def add(a, b):\n    return a + b\nprint(add(3, 4))"
        assert run_py(src).strip() == "7"

    def test_function_with_local_var(self):
        src = "def double(x):\n    result = x * 2\n    return result\nprint(double(5))"
        assert run_py(src).strip() == "10"

    def test_multiple_calls(self):
        src = "def inc(x):\n    return x + 1\nprint(inc(1))\nprint(inc(inc(1)))"
        lines = run_py(src).strip().split("\n")
        assert lines == ["2", "3"]

    def test_recursive_factorial(self):
        src = """def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)
print(fact(5))"""
        assert run_py(src).strip() == "120"

    def test_recursive_fibonacci(self):
        src = """def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
print(fib(10))"""
        assert run_py(src).strip() == "55"


class TestRandom:
    def test_random_range(self):
        src = "import random\nx = random.random()\nprint(x)"
        val = float(run_py(src).strip())
        assert 0.0 <= val < 1.0

    def test_random_in_loop(self):
        src = "import random\ns = 0\nfor i in range(100):\n    s += random.random()\nprint(s)"
        val = float(run_py(src).strip())
        # Sum of 100 uniform [0,1) should be roughly 50
        assert 10 < val < 90


class TestMonteCarloPI:
    def test_pi_estimate(self):
        src = """import random
hits = 0
total = 500
for i in range(total):
    x = random.random()
    y = random.random()
    if x*x + y*y <= 1.0:
        hits += 1
pi = 4.0 * hits / total
print(pi)"""
        val = float(run_py(src).strip())
        assert 2.5 <= val <= 3.8, f"Pi estimate out of range: {val}"


# ── transpile_to_source ──────────────────────────────────────────────────


class TestTranspileToSource:
    def test_produces_emojiasm(self):
        asm = transpile_to_source("print(42)")
        assert len(asm) > 10
        assert "📜" in asm
        assert "🛑" in asm

    def test_roundtrip_execution(self):
        """Transpiled EmojiASM source can be parsed and run."""
        from emojiasm.parser import parse
        asm = transpile_to_source("x = 5\nprint(x + 3)")
        program = parse(asm)
        out = VM(program).run()
        assert "".join(out).strip() == "8"


# ── Error handling ───────────────────────────────────────────────────────


class TestErrors:
    def test_empty_source(self):
        with pytest.raises(TranspileError):
            transpile("")

    def test_syntax_error(self):
        with pytest.raises(TranspileError, match="syntax"):
            transpile("def (")

    def test_string_literal(self):
        with pytest.raises(TranspileError, match="[Ss]tring"):
            transpile("x = 'hello'")

    def test_list_comprehension(self):
        with pytest.raises(TranspileError, match="[Cc]omprehension"):
            transpile("[x for x in range(5)]")

    def test_class_def(self):
        with pytest.raises(TranspileError, match="[Cc]lass"):
            transpile("class Foo: pass")

    def test_lambda(self):
        with pytest.raises(TranspileError, match="[Ll]ambda"):
            transpile("f = lambda x: x")

    def test_unsupported_import(self):
        with pytest.raises(TranspileError, match="[Uu]nsupported import"):
            transpile("import os")

    def test_unassigned_variable(self):
        with pytest.raises(TranspileError, match="before assignment"):
            transpile("print(x)")

    def test_chained_comparison_now_supported(self):
        # Chained comparisons are now supported
        out = run_py("print(1 < 2 < 3)")
        assert out.strip() == "1"

    def test_power_operator_now_supported(self):
        # ** operator is now supported via POW opcode
        out = run_py("print(2 ** 3)")
        assert out.strip() == "8"

    def test_range_too_many_args(self):
        with pytest.raises(TranspileError):
            transpile("for i in range(1,2,3,4):\n    pass")

    def test_non_range_for(self):
        with pytest.raises(TranspileError, match="range"):
            transpile("for x in [1,2,3]:\n    pass")

    def test_none_constant(self):
        with pytest.raises(TranspileError, match="None"):
            transpile("x = None")

    def test_break_outside_loop(self):
        with pytest.raises(TranspileError, match="outside loop"):
            transpile("break")

    def test_continue_outside_loop(self):
        with pytest.raises(TranspileError, match="outside loop"):
            transpile("continue")


# ── EmojiASMTool integration ─────────────────────────────────────────────


class TestToolIntegration:
    def test_execute_python(self):
        from emojiasm import EmojiASMTool
        tool = EmojiASMTool()
        result = tool.execute_python("print(42)", n=1)
        assert result["success"]
        assert result["mode"] == "cpu"

    def test_execute_python_error(self):
        from emojiasm import EmojiASMTool
        tool = EmojiASMTool()
        result = tool.execute_python("class Foo: pass")
        assert not result["success"]
        assert "error" in result


# ── Multi-arg print and edge cases ───────────────────────────────────────


class TestEdgeCases:
    def test_multi_arg_print(self):
        out = run_py("print(1, 2, 3)")
        assert "1" in out and "2" in out and "3" in out

    def test_pass_statement(self):
        assert run_py("x = 5\npass\nprint(x)").strip() == "5"

    def test_empty_while_body(self):
        # while with pass should not crash
        src = "i = 0\nwhile i < 3:\n    i += 1\n    pass\nprint(i)"
        assert run_py(src).strip() == "3"

    def test_print_no_args(self):
        out = run_py("print()")
        assert "\n" in out

    def test_nested_function_calls(self):
        src = "def f(x):\n    return x + 1\nprint(f(f(f(0))))"
        assert run_py(src).strip() == "3"

    def test_complex_expression(self):
        src = "x = 10\ny = 3\nprint((x + y) * (x - y) // 2)"
        assert run_py(src).strip() == "45"


# ── Power operator ───────────────────────────────────────────────────────


class TestPower:
    def test_power_int(self):
        assert run_py("print(2 ** 10)").strip() == "1024"

    def test_power_float(self):
        assert run_py("print(4 ** 0.5)").strip() == "2.0"

    def test_power_augassign(self):
        assert run_py("x = 3\nx **= 2\nprint(x)").strip() == "9"


# ── Math functions ───────────────────────────────────────────────────────


class TestMathFunctions:
    def test_sqrt(self):
        assert run_py("import math\nprint(math.sqrt(16))").strip() == "4.0"

    def test_sin_zero(self):
        assert run_py("import math\nprint(math.sin(0))").strip() == "0.0"

    def test_cos_zero(self):
        assert run_py("import math\nprint(math.cos(0))").strip() == "1.0"

    def test_exp_zero(self):
        assert run_py("import math\nprint(math.exp(0))").strip() == "1.0"

    def test_log_one(self):
        assert run_py("import math\nprint(math.log(1))").strip() == "0.0"

    def test_abs_negative_int(self):
        assert run_py("print(abs(-5))").strip() == "5"

    def test_abs_negative_float(self):
        assert run_py("print(abs(-3.14))").strip() == "3.14"

    def test_min(self):
        assert run_py("print(min(3, 7))").strip() == "3"

    def test_max(self):
        assert run_py("print(max(3, 7))").strip() == "7"


# ── Math constants ───────────────────────────────────────────────────────


class TestMathConstants:
    def test_pi(self):
        out = run_py("import math\nx = math.pi\nprint(x)").strip()
        assert out.startswith("3.14159")

    def test_e(self):
        out = run_py("import math\nx = math.e\nprint(x)").strip()
        assert out.startswith("2.71828")

    def test_pi_in_expression(self):
        out = run_py("import math\nprint(2 * math.pi)").strip()
        val = float(out)
        assert abs(val - 6.283185307179586) < 0.001


# ── Chained comparisons ─────────────────────────────────────────────────


class TestChainedComparisons:
    def test_ascending_true(self):
        assert run_py("print(1 < 2 < 3)").strip() == "1"

    def test_ascending_false(self):
        assert run_py("print(1 < 3 < 2)").strip() == "0"

    def test_triple_chain(self):
        assert run_py("print(1 < 2 < 3 < 4)").strip() == "1"

    def test_mixed_ops(self):
        assert run_py("print(1 <= 2 < 3)").strip() == "1"

    def test_in_if(self):
        src = "x = 5\nif 1 < x < 10:\n    print(1)\nelse:\n    print(0)"
        assert run_py(src).strip() == "1"


# ── Random distributions ────────────────────────────────────────────────


class TestRandomDistributions:
    def test_uniform_in_range(self):
        src = "import random\nx = random.uniform(1, 10)\nprint(x)"
        val = float(run_py(src).strip())
        assert 1.0 <= val < 10.0

    def test_gauss_returns_float(self):
        src = "import random\nx = random.gauss(0, 1)\nprint(x)"
        out = run_py(src).strip()
        # Should produce a float (contains a dot)
        val = float(out)
        assert isinstance(val, float)


# ── Array operations ─────────────────────────────────────────────────────


class TestArrayAlloc:
    def test_array_alloc(self):
        """arr = [0.0] * 5 transpiles and runs."""
        src = "arr = [0.0] * 5\nprint(len(arr))"
        assert run_py(src).strip() == "5"


class TestArraySubscriptRead:
    def test_array_subscript_read(self):
        """arr[0] after assignment returns correct value."""
        src = "arr = [0.0] * 5\narr[0] = 42\nprint(arr[0])"
        assert run_py(src).strip() == "42"


class TestArraySubscriptWrite:
    def test_array_subscript_write(self):
        """arr[i] = value stores correctly."""
        src = "arr = [0.0] * 3\narr[1] = 99\nprint(arr[1])"
        assert run_py(src).strip() == "99"


class TestArrayAugmentedAssign:
    def test_array_augmented_assign(self):
        """arr[i] += value works."""
        src = "arr = [0.0] * 5\narr[2] = 10\narr[2] += 5\nprint(arr[2])"
        assert run_py(src).strip() == "15"


class TestArrayLoopFill:
    def test_array_loop_fill(self):
        """for i in range(N): arr[i] = i*i."""
        src = "arr = [0.0] * 5\nfor i in range(5):\n    arr[i] = i * i\nprint(arr[3])"
        assert run_py(src).strip() == "9"


class TestArraySum:
    def test_array_sum(self):
        """sum(arr) returns correct sum."""
        src = "arr = [0.0] * 3\narr[0] = 1\narr[1] = 2\narr[2] = 3\nprint(sum(arr))"
        assert run_py(src).strip() == "6.0"


class TestArrayLen:
    def test_array_len(self):
        """len(arr) returns correct length."""
        src = "arr = [0.0] * 10\nprint(len(arr))"
        assert run_py(src).strip() == "10"


class TestArraySumFilled:
    def test_array_sum_filled(self):
        """Fill array, sum it, verify."""
        src = "arr = [0.0] * 5\nfor i in range(5):\n    arr[i] = i * i\nprint(sum(arr))"
        # 0 + 1 + 4 + 9 + 16 = 30
        assert run_py(src).strip() == "30.0"


# ── Constant folding ─────────────────────────────────────────────────────


class TestConstantFoldingMul:
    def test_constant_folding_mul(self):
        """4.0 * 3.14159 emits fewer instructions (single PUSH)."""
        from emojiasm.disasm import disassemble
        p = transpile("x = 4.0 * 3.14159\nprint(x)")
        d = disassemble(p)
        # Folded: only 1 PUSH (the folded result), not 3 (two operands + mul)
        assert d.count("📥") == 1


class TestConstantFoldingAdd:
    def test_constant_folding_add(self):
        """10 + 20 folds to single PUSH."""
        from emojiasm.disasm import disassemble
        p = transpile("x = 10 + 20\nprint(x)")
        d = disassemble(p)
        assert d.count("📥") == 1
        assert run_py("x = 10 + 20\nprint(x)").strip() == "30"


class TestConstantFoldingPreservesCorrectness:
    def test_constant_folding_preserves_correctness(self):
        """Folded expression produces same result as unfolded."""
        # Folded: 4.0 * 3.14159 computed at compile time
        folded = run_py("x = 4.0 * 3.14159\nprint(x)").strip()
        # Unfolded: use variable to prevent folding
        unfolded = run_py("a = 4.0\nb = 3.14159\nx = a * b\nprint(x)").strip()
        assert abs(float(folded) - float(unfolded)) < 1e-10


# ── Type inference ───────────────────────────────────────────────────────


class TestTypeInferenceFloatDiv:
    def test_type_inference_float_div(self):
        """x = 1.0; y = x / 2 works correctly (0.5) and skips coercion."""
        from emojiasm.disasm import disassemble
        src = "x = 1.0\ny = x / 2\nprint(y)"
        assert run_py(src).strip() == "0.5"
        # Float var: no coercion needed (no PUSH 1.0 MUL pattern)
        p = transpile(src)
        d = disassemble(p)
        # Should not contain the coercion pattern "📥 1.0\n  ✖" before ➗
        lines = d.split("\n")
        for i, line in enumerate(lines):
            if "➗" in line and i >= 2:
                # The two lines before division should NOT be PUSH 1.0 + MUL
                assert not (lines[i - 2].strip().startswith("📥 1.0") and "✖" in lines[i - 1])


class TestTypeInferenceIntDiv:
    def test_type_inference_int_div(self):
        """7 / 2 still produces 3.5 (coercion still applied)."""
        # Use variable to avoid constant folding
        src = "x = 7\ny = x / 2\nprint(y)"
        assert run_py(src).strip() == "3.5"
        # Int var: coercion should be present
        from emojiasm.disasm import disassemble
        p = transpile(src)
        d = disassemble(p)
        # Should contain the PUSH 1.0 coercion for int division
        assert "📥 1.0" in d


# ── Numpy shim ───────────────────────────────────────────────────────────


class TestNumpyShim:
    def test_numpy_random_random(self):
        src = "import numpy as np\nx = np.random.random()\nprint(x)"
        val = float(run_py(src).strip())
        assert 0.0 <= val < 1.0

    def test_numpy_sqrt(self):
        src = "import numpy as np\nprint(np.sqrt(16))"
        assert run_py(src).strip() == "4.0"

    def test_numpy_pi(self):
        src = "import numpy as np\nprint(np.pi)"
        out = run_py(src).strip()
        assert out.startswith("3.14")

    def test_numpy_random_normal(self):
        src = "import numpy as np\nx = np.random.normal(0, 1)\nprint(x)"
        val = float(run_py(src).strip())
        assert isinstance(val, float)

    def test_numpy_random_uniform(self):
        src = "import numpy as np\nx = np.random.uniform(1, 10)\nprint(x)"
        val = float(run_py(src).strip())
        assert 1.0 <= val < 10.0

    def test_numpy_abs(self):
        src = "import numpy as np\nprint(np.abs(-5))"
        assert run_py(src).strip() == "5"

    def test_numpy_sin_cos(self):
        src = "import numpy as np\nprint(np.sin(0))\nprint(np.cos(0))"
        out = run_py(src).strip()
        assert out == "0.0\n1.0"

    def test_numpy_e(self):
        src = "import numpy as np\nprint(np.e)"
        out = run_py(src).strip()
        assert out.startswith("2.71")


# ── Auto-parallelization ───────────────────────────────────────────────


class TestAutoParallelization:
    def test_single_instance_detection_positive(self):
        """Monte Carlo pi pattern IS detected as single-instance."""
        import ast
        from emojiasm.transpiler import _is_single_instance

        src = (
            "import random\n"
            "x = random.random()\n"
            "y = random.random()\n"
            "result = x*x + y*y <= 1.0"
        )
        tree = ast.parse(src)
        assert _is_single_instance(tree) is True

    def test_single_instance_detection_negative(self):
        """Program with large for-loop is NOT single-instance."""
        import ast
        from emojiasm.transpiler import _is_single_instance

        src = (
            "import random\n"
            "s = 0\n"
            "for i in range(1000):\n"
            "    s += random.random()\n"
            "result = s"
        )
        tree = ast.parse(src)
        assert _is_single_instance(tree) is False

    def test_result_capture(self):
        """Program with result = expr has result value printed after capture."""
        import ast
        from emojiasm.transpiler import _is_single_instance, _ensure_result_capture

        src = (
            "import random\n"
            "x = random.random()\n"
            "result = x * 2"
        )
        tree = ast.parse(src)
        assert _is_single_instance(tree) is True

        tree = _ensure_result_capture(tree)
        unparsed = ast.unparse(tree)
        # Should have appended print(result)
        assert "print(result)" in unparsed

    def test_execute_python_parallel(self):
        """execute_python(source, n=50) returns 50 results."""
        from emojiasm.inference import EmojiASMTool

        tool = EmojiASMTool(prefer_gpu=False)
        src = (
            "import random\n"
            "x = random.random()\n"
            "y = random.random()\n"
            "result = x*x + y*y <= 1.0"
        )
        r = tool.execute_python(src, n=50)
        assert r["completed"] == 50
        assert len(r["results"]) == 50

    def test_parallel_stats_in_result(self):
        """Result from execute_python includes stats with mean, std, etc."""
        from emojiasm.inference import EmojiASMTool

        tool = EmojiASMTool(prefer_gpu=False)
        src = (
            "import random\n"
            "x = random.random()\n"
            "y = random.random()\n"
            "result = x*x + y*y <= 1.0"
        )
        r = tool.execute_python(src, n=50)
        stats = r["stats"]
        assert "mean" in stats
        assert "std" in stats
        assert "min" in stats
        assert "max" in stats
        assert "count" in stats
        # Mean of boolean (0 or 1) should be between 0 and 1
        assert 0.0 <= stats["mean"] <= 1.0


# ── Error message suggestions ───────────────────────────────────────────


class TestErrorMessages:
    def test_error_list_literal_suggestion(self):
        """List literal error suggests fixed-size arrays."""
        with pytest.raises(TranspileError, match=r"\[0\.0\] \* N"):
            transpile("x = [1,2,3]")

    def test_error_non_range_for(self):
        """Non-range for loop error mentions range()."""
        with pytest.raises(TranspileError, match="range"):
            transpile("for x in items:\n    pass")

    def test_error_unsupported_import(self):
        """Unsupported import error suggests random + math."""
        with pytest.raises(TranspileError, match="random.*math|math.*random"):
            transpile("import os")


# ── Source map tests ─────────────────────────────────────────────────────


class TestSourceMap:
    def test_source_map_simple(self):
        """Transpiled program has instructions with populated source field."""
        p = transpile("x = 42\nprint(x)")
        instrs = p.functions["🏠"].instructions
        sources = [i.source for i in instrs if i.source]
        assert len(sources) > 0

    def test_source_map_correct_line(self):
        """First instruction's source should be 'x = 42'."""
        p = transpile("x = 42\nprint(x)")
        first = p.functions["🏠"].instructions[0]
        assert first.source == "x = 42"

    def test_source_map_multiline(self):
        """Multi-line program has correct source for each line's instructions."""
        src = "x = 42\ny = 10\nprint(x + y)"
        p = transpile(src)
        instrs = p.functions["🏠"].instructions

        # Collect unique source lines from instructions
        source_set = {i.source for i in instrs if i.source}
        assert "x = 42" in source_set
        assert "y = 10" in source_set
        assert "print(x + y)" in source_set


# ── Expanded pool limits ─────────────────────────────────────────────────


class TestVariablePool:
    def test_variable_pool_size(self):
        """EMOJI_POOL must have at least 200 entries."""
        assert len(EMOJI_POOL) >= 200

    def test_variable_pool_no_duplicates(self):
        """All entries in EMOJI_POOL must be unique."""
        assert len(set(EMOJI_POOL)) == len(EMOJI_POOL)

    def test_many_variables(self):
        """Transpile+run a program using 100+ unique variables."""
        # Generate: v0 = 0\nv1 = 1\n...\nv99 = 99\nprint(v0 + v99)
        lines = [f"v{i} = {i}" for i in range(100)]
        lines.append("print(v0 + v99)")
        src = "\n".join(lines)
        assert run_py(src).strip() == "99"


class TestFunctionPool:
    def test_function_pool_size(self):
        """FUNC_EMOJI_POOL must have at least 50 entries."""
        assert len(FUNC_EMOJI_POOL) >= 50

    def test_many_functions(self):
        """Transpile+run a program with 30+ def statements."""
        # Generate: def f0(): return 0\ndef f1(): return 1\n...\ndef f29(): return 29\nprint(f29())
        lines = [f"def f{i}():\n    return {i}" for i in range(30)]
        lines.append("print(f29())")
        src = "\n".join(lines)
        assert run_py(src).strip() == "29"
