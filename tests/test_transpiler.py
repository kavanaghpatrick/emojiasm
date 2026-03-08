"""Tests for the Python-to-EmojiASM transpiler."""

import pytest
from emojiasm.transpiler import transpile, transpile_to_source, TranspileError
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
