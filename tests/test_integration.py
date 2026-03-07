"""End-to-end integration tests for EmojiASM.

Each test embeds its program as a string literal and runs it through the full
parse -> VM pipeline, then asserts on the collected output.
"""

from emojiasm.parser import parse
from emojiasm.vm import VM


def run(source: str, max_steps: int = 2_000_000) -> str:
    program = parse(source)
    vm = VM(program)
    vm.max_steps = max_steps
    vm.run()
    return "".join(vm.output_buffer)


# ---------------------------------------------------------------------------
# 1. Fibonacci sequence (from examples/fibonacci.emoji)
#    Prints the first 20 Fibonacci numbers separated by spaces.
# ---------------------------------------------------------------------------

FIBONACCI_SOURCE = """\
💭 Fibonacci sequence
💭 Prints first 20 Fibonacci numbers

📜 🏠
  💬 "Fibonacci: "
  📢

  📥 0
  💾 🅰️
  📥 1
  💾 🅱️
  📥 0
  💾 🔢

🏷️ 🔁
  📂 🔢
  📥 20
  🟰
  😤 🏁

  💭 Print current number
  📂 🅰️
  📢
  💬 " "
  📢

  💭 Compute next: temp = a + b, a = b, b = temp
  📂 🅰️
  📂 🅱️
  ➕
  💾 🌡️

  📂 🅱️
  💾 🅰️
  📂 🌡️
  💾 🅱️

  💭 Increment counter
  📂 🔢
  📥 1
  ➕
  💾 🔢

  👉 🔁

🏷️ 🏁
  💬 "\\n"
  📢
  🛑
"""


def test_fibonacci():
    output = run(FIBONACCI_SOURCE)
    # The first 20 Fibonacci numbers starting from F(0)=0
    expected_numbers = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233,
                        377, 610, 987, 1597, 2584, 4181]
    for n in expected_numbers:
        assert str(n) in output, (
            f"Expected Fibonacci number {n} in output, got: {output!r}"
        )
    # Verify ordering: the numbers appear left-to-right in the correct sequence
    positions = [output.index(str(n)) for n in [0, 1, 2, 3, 5, 8, 13, 21, 34, 55]]
    assert positions == sorted(positions), "Fibonacci numbers are out of order"


# ---------------------------------------------------------------------------
# 2. Sum of 1..50000 (from benchmarks/sum_n.emoji)
#    Result must be 1250025000.
# ---------------------------------------------------------------------------

SUM_N_SOURCE = """\
💭 Benchmark: sum integers 1..50000
💭 Result should be 1250025000
💭 Loop exits when i > 50000 (CMP_GT pops b=50000, a=i, pushes 1 if i > 50000)

📜 🏠
  📥 0
  💾 🧮
  📥 1
  💾 🔢

🏷️ 🔁
  📂 🔢
  📥 50000
  📐
  😤 🏁

  📂 🧮
  📂 🔢
  ➕
  💾 🧮

  📂 🔢
  📥 1
  ➕
  💾 🔢

  👉 🔁

🏷️ 🏁
  📂 🧮
  🖨️
  🛑
"""


def test_sum_n():
    output = run(SUM_N_SOURCE, max_steps=5_000_000)
    assert output.strip() == "1250025000", (
        f"Expected 1250025000, got: {output.strip()!r}"
    )


# ---------------------------------------------------------------------------
# 3. Factorial of 10 (iterative)
#    10! = 3628800
#
#    acc = 1, i = 1
#    loop: if i > 10 -> halt
#          acc = acc * i
#          i = i + 1
#          repeat
# ---------------------------------------------------------------------------

FACTORIAL_SOURCE = """\
💭 Iterative factorial: computes 10! = 3628800

📜 🏠
  📥 1
  💾 🪣
  📥 1
  💾 🔢

🏷️ 🔁
  📂 🔢
  📥 10
  📐
  😤 🏁

  📂 🪣
  📂 🔢
  ✖️
  💾 🪣

  📂 🔢
  📥 1
  ➕
  💾 🔢

  👉 🔁

🏷️ 🏁
  📂 🪣
  🖨️
  🛑
"""


def test_factorial():
    output = run(FACTORIAL_SOURCE)
    assert output.strip() == "3628800", (
        f"Expected 3628800, got: {output.strip()!r}"
    )


# ---------------------------------------------------------------------------
# 4. Fibonacci iterative — first 10 numbers printed one per line
#    0, 1, 1, 2, 3, 5, 8, 13, 21, 34
#
#    Uses PRINTLN so each number is on its own line; easy to split and verify.
# ---------------------------------------------------------------------------

FIBONACCI_ITERATIVE_SOURCE = """\
💭 Print the first 10 Fibonacci numbers, one per line

📜 🏠
  📥 0
  💾 🅰️
  📥 1
  💾 🅱️
  📥 0
  💾 🔢

🏷️ 🔁
  📂 🔢
  📥 10
  🟰
  😤 🏁

  📂 🅰️
  🖨️

  📂 🅰️
  📂 🅱️
  ➕
  💾 🌡️

  📂 🅱️
  💾 🅰️
  📂 🌡️
  💾 🅱️

  📂 🔢
  📥 1
  ➕
  💾 🔢

  👉 🔁

🏷️ 🏁
  🛑
"""


def test_fibonacci_iterative():
    output = run(FIBONACCI_ITERATIVE_SOURCE)
    lines = [ln.strip() for ln in output.strip().splitlines() if ln.strip()]
    expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
    assert len(lines) == len(expected), (
        f"Expected {len(expected)} lines, got {len(lines)}: {lines}"
    )
    for i, (got, exp) in enumerate(zip(lines, expected)):
        assert got == str(exp), (
            f"Fibonacci[{i}]: expected {exp}, got {got!r}"
        )


# ---------------------------------------------------------------------------
# 5. String operations
#    Demonstrates PRINTS (💬) to push string literals, ADD (➕) for concat,
#    and PRINT / PRINTLN for output.
#
#    Program builds "Hello, EmojiASM!" via string concat and prints it,
#    then concatenates a number onto a string label and prints that.
# ---------------------------------------------------------------------------

STRING_OPS_SOURCE = """\
💭 String operations demo

📜 🏠
  💭 Concat two string literals
  💬 "Hello, "
  💬 "EmojiASM!"
  ➕
  🖨️

  💭 Concat a number result onto a string: "Answer: " + str(6*7)
  📥 6
  📥 7
  ✖️
  💬 "Answer: "
  🔀
  ➕
  🖨️

  🛑
"""


def test_string_operations():
    output = run(STRING_OPS_SOURCE)
    lines = output.strip().splitlines()
    # First line: string concat of two literals
    assert lines[0].strip() == "Hello, EmojiASM!", (
        f"Expected 'Hello, EmojiASM!', got: {lines[0]!r}"
    )
    # Second line: "Answer: " + str(42)
    assert lines[1].strip() == "Answer: 42", (
        f"Expected 'Answer: 42', got: {lines[1]!r}"
    )


# ---------------------------------------------------------------------------
# 6. If / then / else branching
#    STOREs a value to a cell, LOADs it, compares with a threshold,
#    and routes to one of two print paths.
#
#    Pattern:
#      LOAD val; PUSH threshold; CMP_GT; JZ false_branch
#      [true branch] print "big"; JMP done
#      [false branch] print "small"
#      [done] HALT
#
#    We run two separate programs: one where the condition is true,
#    one where it is false.
# ---------------------------------------------------------------------------

IF_ELSE_TRUE_SOURCE = """\
💭 If/else: value (42) > threshold (10) -> prints "big"

📜 🏠
  📥 42
  💾 🎯

  📂 🎯
  📥 10
  📐
  🤔 🔴

  💬 "big"
  🖨️
  👉 🏁

🏷️ 🔴
  💬 "small"
  🖨️

🏷️ 🏁
  🛑
"""

IF_ELSE_FALSE_SOURCE = """\
💭 If/else: value (3) > threshold (10) -> prints "small"

📜 🏠
  📥 3
  💾 🎯

  📂 🎯
  📥 10
  📐
  🤔 🔴

  💬 "big"
  🖨️
  👉 🏁

🏷️ 🔴
  💬 "small"
  🖨️

🏷️ 🏁
  🛑
"""


def test_if_then_else():
    # When stored value (42) > threshold (10): CMP_GT pushes 1, JZ does NOT jump
    output_true = run(IF_ELSE_TRUE_SOURCE)
    assert output_true.strip() == "big", (
        f"Expected 'big' for value=42, threshold=10; got: {output_true.strip()!r}"
    )

    # When stored value (3) > threshold (10): CMP_GT pushes 0, JZ DOES jump
    output_false = run(IF_ELSE_FALSE_SOURCE)
    assert output_false.strip() == "small", (
        f"Expected 'small' for value=3, threshold=10; got: {output_false.strip()!r}"
    )


# ---------------------------------------------------------------------------
# 7. Function with result: square(n) = n * n, called multiple times
#    (from examples/functions.emoji)
#
#    Calls square(5)=25, square(12)=144, square(7)=49.
# ---------------------------------------------------------------------------

SQUARE_FUNCTION_SOURCE = """\
💭 Function call demo
💭 Defines a "square" function and calls it

📜 🏠
  💬 "5 squared = "
  📢
  📥 5
  📞 🔲
  🖨️

  💬 "12 squared = "
  📢
  📥 12
  📞 🔲
  🖨️

  💬 "7 squared = "
  📢
  📥 7
  📞 🔲
  🖨️

  🛑

💭 Square function: pops top of stack, pushes its square
📜 🔲
  📋
  ✖️
  📲
"""


def test_function_with_result():
    output = run(SQUARE_FUNCTION_SOURCE)
    assert "5 squared = 25" in output, (
        f"Expected '5 squared = 25' in output, got: {output!r}"
    )
    assert "12 squared = 144" in output, (
        f"Expected '12 squared = 144' in output, got: {output!r}"
    )
    assert "7 squared = 49" in output, (
        f"Expected '7 squared = 49' in output, got: {output!r}"
    )
    # Verify ordering
    pos_5 = output.index("5 squared")
    pos_12 = output.index("12 squared")
    pos_7 = output.index("7 squared")
    assert pos_5 < pos_12 < pos_7, "Functions called out of expected order"
