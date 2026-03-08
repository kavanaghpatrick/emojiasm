---
spec: python-transpiler
phase: tasks
total_tasks: 22
created: 2026-03-08
generated: auto
---

# Tasks: Python-to-EmojiASM Transpiler

## Phase 1: Make It Work (POC)

Focus: Get arithmetic expressions + variables + print working end-to-end. Skip tests, accept minimal error handling.

- [ ] 1.1 Scaffold transpiler module with core classes
  - **Do**: Create `emojiasm/transpiler.py` with:
    - `TranspileError` exception class (mirrors `ParseError` pattern from `parser.py`)
    - `VarManager` class with `assign(name, scope)` -> emoji str, `lookup(name, scope)` -> emoji str, `is_assigned(name, scope)` -> bool. Uses `EMOJI_POOL` list of 50 emoji characters, assigns sequentially.
    - `LabelGenerator` class with `next(prefix)` -> str. Counter-based: returns `"L1"`, `"L2"`, etc.
    - `PythonTranspiler(ast.NodeVisitor)` class skeleton with `__init__` (program, current_func, vars, labels, loop_stack), `transpile(source: str) -> Program` method that calls `ast.parse()` and `self.visit()`.
    - Module-level `transpile(source: str) -> Program` function
    - Module-level `transpile_to_source(source: str) -> str` function using `disassemble()`
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: Module imports without errors; `transpile("")` raises `TranspileError`
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile, transpile_to_source, TranspileError; print('OK')"`
  - **Commit**: `feat(transpiler): scaffold module with core classes`
  - _Requirements: FR-18, FR-19, FR-22_
  - _Design: Component A, B, C_

- [ ] 1.2 Compile integer/float literals and print
  - **Do**: Implement these visitor methods on `PythonTranspiler`:
    - `visit_Module(node)`: create main function `🏠`, visit body statements, append `HALT`
    - `visit_Expr(node)`: visit the expression value (for standalone expression statements)
    - `visit_Constant(node)`: emit `Instruction(Op.PUSH, node.value)` for int/float. Raise `TranspileError` for string/other constants.
    - `visit_Call(node)`: detect `print(expr)` specifically -- visit the argument expression, then emit `Instruction(Op.PRINTLN)`. For now, only handle single-argument print.
    - Helper `_emit(op, arg=None, node=None)`: append `Instruction` to current function with line number from AST node.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("print(42)")` produces a valid `Program` that VM executes and outputs `"42\n"`
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.vm import VM; p = transpile('print(42)'); vm = VM(p); out = vm.run(); assert ''.join(out).strip() == '42', out; print('OK')"`
  - **Commit**: `feat(transpiler): compile literals and print()`
  - _Requirements: FR-1, FR-14, FR-25_
  - _Design: Component D (visit_Constant), Component E (visit_Expr)_

- [ ] 1.3 Compile binary arithmetic operators
  - **Do**: Implement `visit_BinOp(node)`:
    - Visit `node.left` (pushes left value)
    - Visit `node.right` (pushes right value)
    - Map `ast.Add`->`Op.ADD`, `ast.Sub`->`Op.SUB`, `ast.Mult`->`Op.MUL`, `ast.Mod`->`Op.MOD`, `ast.FloorDiv`->`Op.DIV`
    - For `ast.Div` (true division): visit left, emit `PUSH 1.0` + `MUL` to coerce to float, visit right, emit `DIV`
    - Emit the corresponding EmojiASM op
    - Raise `TranspileError` for unsupported ops (`ast.Pow`, `ast.BitOr`, etc.)
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("print(3 + 4 * 5)")` produces Program that outputs `"23"` when run on VM
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.vm import VM; p = transpile('print(3 + 4 * 5)'); out = VM(p).run(); assert ''.join(out).strip() == '23', out; print('OK')"`
  - **Commit**: `feat(transpiler): compile binary arithmetic operators`
  - _Requirements: FR-2, FR-3, FR-23_
  - _Design: Component D (visit_BinOp), Operator Mapping_

- [ ] 1.4 Compile unary operators
  - **Do**: Implement `visit_UnaryOp(node)`:
    - `ast.USub` (-x): emit `PUSH 0`, visit operand, emit `SUB`
    - `ast.UAdd` (+x): just visit operand (no-op)
    - `ast.Not` (not x): visit operand, emit `NOT`
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("print(-5)")` outputs `"-5"` and `transpile("print(not 0)")` outputs `"1"`
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.vm import VM; p = transpile('print(-5)'); out = VM(p).run(); assert ''.join(out).strip() == '-5', out; p2 = transpile('print(not 0)'); out2 = VM(p2).run(); assert ''.join(out2).strip() == '1', out2; print('OK')"`
  - **Commit**: `feat(transpiler): compile unary operators`
  - _Requirements: FR-2, FR-8_
  - _Design: Component D (visit_UnaryOp)_

- [ ] 1.5 Compile variable assignment and read
  - **Do**: Implement:
    - `visit_Assign(node)`: visit value expression, then for each target in `node.targets`, if it's `ast.Name`, call `_vars.assign(target.id)` to get emoji cell, emit `STORE cell`. For multi-target (a = b = 5), DUP before each STORE except the last.
    - `visit_Name(node)`: call `_vars.lookup(node.id)` to get emoji cell, emit `LOAD cell`. If variable not assigned, raise `TranspileError`.
    - `visit_AugAssign(node)`: LOAD target, visit value, emit binop, STORE target.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("x = 5\ny = x + 3\nprint(y)")` outputs `"8"`
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.vm import VM; p = transpile('x = 5\ny = x + 3\nprint(y)'); out = VM(p).run(); assert ''.join(out).strip() == '8', out; print('OK')"`
  - **Commit**: `feat(transpiler): compile variable assignment and read`
  - _Requirements: FR-4, FR-5, FR-6_
  - _Design: Component B (VarManager), Component E (visit_Assign)_

- [ ] 1.6 Compile comparison and boolean operators
  - **Do**: Implement:
    - `visit_Compare(node)`: visit left, visit first comparator, emit comparison op. Map: `ast.Eq`->`CMP_EQ`, `ast.NotEq`->`CMP_EQ`+`NOT`, `ast.Lt`->`CMP_LT`, `ast.Gt`->`CMP_GT`, `ast.LtE`->`CMP_GT`+`NOT`, `ast.GtE`->`CMP_LT`+`NOT`. For chained comparisons (len(ops) > 1), raise `TranspileError` with suggestion.
    - `visit_BoolOp(node)`: for `ast.And`, visit values[0], then for each subsequent value, visit it and emit `AND`. Same for `ast.Or` with `OR`.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("x = 5\nprint(x == 5)")` outputs `"1"` and `transpile("print(1 < 2 and 3 > 1)")` outputs `"1"`
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.vm import VM; p = transpile('x = 5\nprint(x == 5)'); out = VM(p).run(); assert ''.join(out).strip() == '1', out; p2 = transpile('print(1 < 2 and 3 > 1)'); out2 = VM(p2).run(); assert ''.join(out2).strip() == '1', out2; print('OK')"`
  - **Commit**: `feat(transpiler): compile comparison and boolean operators`
  - _Requirements: FR-7, FR-8_
  - _Design: Component D (visit_Compare, visit_BoolOp), Comparison Operators table_

- [ ] 1.7 Compile if/elif/else statements
  - **Do**: Implement `visit_If(node)`:
    - **if-only**: visit test, emit `JZ end_label`, compile body, `end_label:`
    - **if-else**: visit test, emit `JZ else_label`, compile body, emit `JMP end_label`, `else_label:`, compile orelse body, `end_label:`
    - **if-elif-else**: The AST nests elif as an `If` inside `orelse`. Check if `orelse` is a single `If` node -- if so, chain labels. Otherwise compile as if-else.
    - Use `LabelGenerator` for unique labels.
    - Labels added to `current_func.labels` dict mapping to current instruction index.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("x = 5\nif x > 3:\n    print(1)\nelse:\n    print(0)")` outputs `"1"`
  - **Verify**: `python3 -c "
from emojiasm.transpiler import transpile
from emojiasm.vm import VM
src = 'x = 5\nif x > 3:\n    print(1)\nelse:\n    print(0)'
out = VM(transpile(src)).run()
assert ''.join(out).strip() == '1', out
src2 = 'x = 1\nif x > 5:\n    print(1)\nelif x > 0:\n    print(2)\nelse:\n    print(3)'
out2 = VM(transpile(src2)).run()
assert ''.join(out2).strip() == '2', out2
print('OK')
"`
  - **Commit**: `feat(transpiler): compile if/elif/else statements`
  - _Requirements: FR-9_
  - _Design: Component E (visit_If), Control Flow Compilation_

- [ ] 1.8 Compile while loops
  - **Do**: Implement `visit_While(node)`:
    - Generate `loop_label` and `end_label`
    - Set `loop_label:` at current instruction index
    - Visit test condition, emit `JZ end_label`
    - Push `(loop_label, end_label)` onto `_loop_stack`
    - Compile body statements
    - Emit `JMP loop_label`
    - Set `end_label:` at current instruction index
    - Pop `_loop_stack`
  - Also implement `visit_Break(node)`:
    - Check `_loop_stack` is not empty (else TranspileError)
    - Emit `JMP break_label` where break_label is the end_label from top of `_loop_stack`
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("i = 0\nwhile i < 5:\n    i += 1\nprint(i)")` outputs `"5"`
  - **Verify**: `python3 -c "
from emojiasm.transpiler import transpile
from emojiasm.vm import VM
src = 'i = 0\nwhile i < 5:\n    i += 1\nprint(i)'
out = VM(transpile(src)).run()
assert ''.join(out).strip() == '5', out
print('OK')
"`
  - **Commit**: `feat(transpiler): compile while loops and break`
  - _Requirements: FR-10, FR-12_
  - _Design: Component E (visit_While, visit_Break), While Loop Pattern_

- [ ] 1.9 Compile for-range loops
  - **Do**: Implement `visit_For(node)`:
    - Validate `node.iter` is a `Call` to `range` with 1-3 args. Raise `TranspileError` otherwise.
    - Validate `node.target` is `ast.Name`. Raise `TranspileError` otherwise.
    - Decompose:
      - `range(n)` -> start=0, stop=n, step=1
      - `range(a, b)` -> start=a, stop=b, step=1
      - `range(a, b, s)` -> start=a, stop=b, step=s
    - Emit: assign start to iterator variable, loop_label, load iterator, compile stop, CMP_LT (or CMP_GT+NOT for negative step check if step is constant negative), JZ end_label, body, load iterator, compile step, ADD, store iterator, JMP loop_label, end_label.
    - Push to `_loop_stack` for break support.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("s = 0\nfor i in range(5):\n    s += i\nprint(s)")` outputs `"10"`
  - **Verify**: `python3 -c "
from emojiasm.transpiler import transpile
from emojiasm.vm import VM
src = 's = 0\nfor i in range(5):\n    s += i\nprint(s)'
out = VM(transpile(src)).run()
assert ''.join(out).strip() == '10', out
src2 = 's = 0\nfor i in range(2, 5):\n    s += i\nprint(s)'
out2 = VM(transpile(src2)).run()
assert ''.join(out2).strip() == '9', out2
print('OK')
"`
  - **Commit**: `feat(transpiler): compile for-range loops`
  - _Requirements: FR-11_
  - _Design: Component E (visit_For), For-Range Decomposition_

- [ ] 1.10 Compile random.random() and imports
  - **Do**: Implement:
    - `visit_Import(node)`: check each alias name against whitelist `{"random", "math"}`. Raise `TranspileError` for others. Track imported modules in `self._imports: set[str]`.
    - `visit_ImportFrom(node)`: check module against whitelist. Track imported names.
    - Update `visit_Call(node)` to detect:
      - `random.random()`: emit `RANDOM` opcode
      - `math.sqrt(x)`: visit x, emit `PUSH 0.5`, `PUSH 1.0`, `MUL` (coerce float), then implement as `x ** 0.5` -> this is complex without POW. Alternative: emit `PUSH 0.5` as argument, then need a power function. Simplest: skip `math.sqrt()` for now, document as TODO.
    - Handle attribute access: `visit_Attribute(node)` to resolve `random.random` etc.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("import random\nx = random.random()\nprint(x)")` produces Program with RANDOM opcode that runs on VM
  - **Verify**: `python3 -c "
from emojiasm.transpiler import transpile
from emojiasm.vm import VM
src = 'import random\nx = random.random()\nprint(x)'
p = transpile(src)
out = VM(p).run()
val = float(''.join(out).strip())
assert 0.0 <= val < 1.0, f'random value out of range: {val}'
print('OK')
"`
  - **Commit**: `feat(transpiler): compile random.random() and import validation`
  - _Requirements: FR-13, FR-24_
  - _Design: Component D (visit_Call), Component E (visit_Import)_

- [ ] 1.11 Compile function definitions and calls
  - **Do**: Implement:
    - `visit_FunctionDef(node)`: create new `Function` with emoji name from `FUNC_EMOJI_POOL`. Store parameter names. Enter function scope. For each param (in reverse order, since stack is LIFO), emit `STORE param_cell`. Compile body. Ensure function ends with `RET`. Exit function scope. Add to `self.program.functions`.
    - Update `visit_Call(node)` to detect user-defined function calls: visit each argument (left to right), emit `CALL func_emoji`. Result is on stack.
    - `visit_Return(node)`: visit value expression (leaves result on stack), emit `RET`.
    - Pre-scan: do a first pass over the module body to collect function names and their emoji mappings before compiling, so forward references work.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("def square(x):\n    return x * x\nprint(square(7))")` outputs `"49"`
  - **Verify**: `python3 -c "
from emojiasm.transpiler import transpile
from emojiasm.vm import VM
src = 'def square(x):\n    return x * x\nprint(square(7))'
out = VM(transpile(src)).run()
assert ''.join(out).strip() == '49', out
print('OK')
"`
  - **Commit**: `feat(transpiler): compile function definitions and calls`
  - _Requirements: FR-15, FR-16, FR-17_
  - _Design: Component E (visit_FunctionDef), Function Compilation_

- [ ] 1.12 POC Checkpoint: Monte Carlo Pi
  - **Do**: Verify the full transpiler works end-to-end with the Monte Carlo Pi example from the goal:
    ```python
    import random
    hits = 0
    total = 10000
    for i in range(total):
        x = random.random()
        y = random.random()
        if x*x + y*y <= 1.0:
            hits += 1
    pi = 4.0 * hits / total
    print(pi)
    ```
    Run it through `transpile()` -> `VM.run()` and verify output is a reasonable Pi estimate (between 2.9 and 3.3). Also verify `transpile_to_source()` produces readable EmojiASM. Fix any bugs encountered.
  - **Files**: `emojiasm/transpiler.py` (bug fixes only)
  - **Done when**: Monte Carlo Pi produces a value between 2.9 and 3.3; `transpile_to_source()` returns valid EmojiASM text
  - **Verify**: `python3 -c "
from emojiasm.transpiler import transpile, transpile_to_source
from emojiasm.vm import VM
src = '''import random
hits = 0
total = 1000
for i in range(total):
    x = random.random()
    y = random.random()
    if x*x + y*y <= 1.0:
        hits += 1
pi = 4.0 * hits / total
print(pi)'''
p = transpile(src)
out = VM(p).run()
val = float(''.join(out).strip())
assert 2.9 <= val <= 3.3, f'Pi estimate out of range: {val}'
asm = transpile_to_source(src)
assert len(asm) > 50, 'EmojiASM source too short'
print(f'Pi = {val}')
print('EmojiASM source ({} chars):'.format(len(asm)))
print(asm[:200])
print('OK')
"`
  - **Commit**: `feat(transpiler): complete POC - Monte Carlo Pi works`
  - _Requirements: All FR-*_
  - _Design: Full pipeline_

## Phase 2: Refactoring

After POC validated, clean up code and improve robustness.

- [ ] 2.1 Improve error messages and unsupported syntax handling
  - **Do**: Add `generic_visit(node)` method that raises `TranspileError` with the node type name, line number, and suggestions for common cases:
    - `ast.ListComp` -> "List comprehensions not supported. Use a for loop."
    - `ast.DictComp` -> "Dict comprehensions not supported."
    - `ast.ClassDef` -> "Classes not supported."
    - `ast.Try` -> "Try/except not supported."
    - `ast.Lambda` -> "Lambda not supported. Use def."
    - `ast.Yield` -> "Generators not supported."
    - `ast.FormattedValue` / `ast.JoinedStr` -> "f-strings not supported. Use print()."
    - All other nodes -> "Unsupported Python syntax: {node_type} at line {line}."
    Also validate that `visit_Constant` rejects non-numeric constants (strings, None, True, False). Note: True/False should map to 1/0 for convenience.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: All unsupported syntax produces a clear `TranspileError` with line number
  - **Verify**: `python3 -c "
from emojiasm.transpiler import transpile, TranspileError
tests = [
    ('[x for x in range(5)]', 'comprehension'),
    ('class Foo: pass', 'class'),
    ('lambda x: x', 'lambda'),
]
for src, expected_word in tests:
    try:
        transpile(src)
        assert False, f'Should have raised for: {src}'
    except TranspileError as e:
        assert expected_word.lower() in str(e).lower(), f'Missing \"{expected_word}\" in: {e}'
print('OK')
"`
  - **Commit**: `refactor(transpiler): improve error messages for unsupported syntax`
  - _Requirements: FR-22_
  - _Design: Error Handling table_

- [ ] 2.2 Handle edge cases and robustness
  - **Do**:
    - Handle `print()` with no args (emit newline: PUSH empty string is not great; instead just push 0 and PRINTLN, or PUSH "" and PRINTS+PRINTLN)
    - Handle `print(a, b, c)` with multiple args: for each arg, visit it, PRINTLN (or PRINT with space separator). For `print(a, b)`: visit a, PRINT, PUSH " " via PRINTS, PRINT, visit b, PRINTLN.
    - Handle `print(expr, end="")`: detect `end=""` keyword arg, use PRINT instead of PRINTLN.
    - Handle `True` and `False` constants: map to PUSH 1 and PUSH 0.
    - Handle `None`: raise TranspileError.
    - Handle empty function body: emit at least NOP + RET.
    - Handle `pass` statement: emit NOP.
    - Ensure division by zero in transpiled code produces proper VM error (inherits from VM).
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: Multi-arg print works; True/False work; edge cases don't crash
  - **Verify**: `python3 -c "
from emojiasm.transpiler import transpile
from emojiasm.vm import VM
# Multi-arg print
out = VM(transpile('print(1, 2, 3)')).run()
assert '1 2 3' in ''.join(out), out
# Boolean constants
out2 = VM(transpile('print(True)')).run()
assert ''.join(out2).strip() == '1', out2
# pass
out3 = VM(transpile('x = 5\npass\nprint(x)')).run()
assert ''.join(out3).strip() == '5', out3
print('OK')
"`
  - **Commit**: `refactor(transpiler): handle edge cases and multi-arg print`
  - _Design: Error Handling, Component D_

- [ ] 2.3 Add CLI integration (--from-python and --transpile flags)
  - **Do**: Modify `emojiasm/__main__.py`:
    - Add `--from-python` argument: takes a `.py` file path. Read it, call `transpile()`, then proceed with the same execution logic (VM, GPU, compile, etc.) as for `.emoji` files.
    - Add `--transpile` argument: takes a `.py` file path. Calls `transpile_to_source()` and prints the EmojiASM text to stdout.
    - The `--from-python` flag should compose with `--gpu`, `--compile`, `--disasm`, `--agent-mode`, etc.
    - Handle `TranspileError` with user-friendly error output to stderr.
  - **Files**: `emojiasm/__main__.py`
  - **Done when**: `emojiasm --transpile examples_py/hello.py` outputs EmojiASM source; `emojiasm --from-python examples_py/hello.py` runs it
  - **Verify**: `python3 -c "
# Test by importing and checking the argparse setup
from emojiasm.__main__ import main
import sys
sys.argv = ['emojiasm', '--help']
try:
    main()
except SystemExit:
    pass
" 2>&1 | grep -q "from-python" && echo "OK" || echo "FAIL"`
  - **Commit**: `feat(cli): add --from-python and --transpile flags`
  - _Requirements: FR-21_
  - _Design: File Structure (__main__.py modification)_

- [ ] 2.4 Add EmojiASMTool.execute_python() integration
  - **Do**: Modify `emojiasm/inference.py`:
    - Add `execute_python(self, source: str, n: int = 1) -> dict` method to `EmojiASMTool`
    - Implementation: call `transpile(source)` to get Program, then call `self.execute_from_program(program, n)` (extract shared logic from `execute()`).
    - Refactor `execute()` to share code with `execute_python()` (parse step differs, rest is same).
    - Handle `TranspileError` same way as `ParseError`.
    - Update `__init__.py` to export `transpile` and `transpile_to_source`.
  - **Files**: `emojiasm/inference.py`, `emojiasm/__init__.py`
  - **Done when**: `EmojiASMTool().execute_python("print(42)", n=1)` returns structured result
  - **Verify**: `python3 -c "
from emojiasm import EmojiASMTool
tool = EmojiASMTool()
result = tool.execute_python('print(42)', n=1)
assert result['success'], result
print('OK')
"`
  - **Commit**: `feat(inference): add execute_python() to EmojiASMTool`
  - _Requirements: FR-20_
  - _Design: File Structure (inference.py modification)_

## Phase 3: Testing

- [ ] 3.1 Unit tests for expression compilation
  - **Do**: Create `tests/test_transpiler.py` with:
    - `run_py(source)` helper: calls `transpile(source)` then `VM(p).run()`, returns output
    - Test integer literals: `print(42)` -> `"42"`
    - Test float literals: `print(3.14)` -> `"3.14"`
    - Test all arithmetic ops: `+`, `-`, `*`, `//`, `%` with various operands
    - Test true division `/`: `print(7 / 2)` -> `"3.5"`
    - Test operator precedence: `print(2 + 3 * 4)` -> `"14"`
    - Test parenthesized expressions: `print((2 + 3) * 4)` -> `"20"`
    - Test unary negation: `print(-5)` -> `"-5"`
    - Test unary not: `print(not 0)` -> `"1"`
    - Test all comparison ops: `==`, `!=`, `<`, `>`, `<=`, `>=`
    - Test boolean ops: `and`, `or`, `not` combinations
    - Test True/False constants
  - **Files**: `tests/test_transpiler.py`
  - **Done when**: All expression tests pass
  - **Verify**: `cd /Users/patrickkavanagh/emojiasm && pytest tests/test_transpiler.py -k "test_" -v --tb=short 2>&1 | tail -5`
  - **Commit**: `test(transpiler): add expression compilation tests`
  - _Requirements: AC-1.1 through AC-1.5, AC-3.4, AC-3.5_

- [ ] 3.2 Unit tests for variables and assignment
  - **Do**: Add tests to `tests/test_transpiler.py`:
    - Test simple assignment: `x = 5; print(x)` -> `"5"`
    - Test multiple variables: `x = 3; y = 4; print(x + y)` -> `"7"`
    - Test augmented assignment: `x = 5; x += 3; print(x)` -> `"8"` (also `-=`, `*=`, `//=`, `%=`)
    - Test variable reassignment: `x = 1; x = 2; print(x)` -> `"2"`
    - Test unassigned variable raises `TranspileError`
    - Test multi-target assignment: `a = b = 5; print(a); print(b)` -> `"5\n5"`
  - **Files**: `tests/test_transpiler.py`
  - **Done when**: All variable tests pass
  - **Verify**: `cd /Users/patrickkavanagh/emojiasm && pytest tests/test_transpiler.py -k "var" -v --tb=short`
  - **Commit**: `test(transpiler): add variable and assignment tests`
  - _Requirements: AC-2.1 through AC-2.5_

- [ ] 3.3 Unit tests for control flow
  - **Do**: Add tests to `tests/test_transpiler.py`:
    - Test if-only: `if True: print(1)` -> `"1"`
    - Test if-else: branch taken and not taken
    - Test if-elif-else: all branches
    - Test while loop with counter
    - Test for-range with 1, 2, 3 args
    - Test nested loops
    - Test break in while loop
    - Test break in for loop
    - Test nested if inside loop
    - Test loop with conditional increment (Monte Carlo pattern)
  - **Files**: `tests/test_transpiler.py`
  - **Done when**: All control flow tests pass
  - **Verify**: `cd /Users/patrickkavanagh/emojiasm && pytest tests/test_transpiler.py -k "control or loop or if_" -v --tb=short`
  - **Commit**: `test(transpiler): add control flow tests`
  - _Requirements: AC-3.1 through AC-3.5, AC-4.1 through AC-4.6_

- [ ] 3.4 Unit tests for functions and random
  - **Do**: Add tests to `tests/test_transpiler.py`:
    - Test simple function def + call
    - Test function with multiple params
    - Test recursive function (factorial or fibonacci)
    - Test `random.random()` produces value in [0, 1)
    - Test unsupported import raises error
    - Test Monte Carlo Pi integration (approximate check: 2.5 < pi < 3.8 for small n=100)
    - Test `transpile_to_source()` produces valid EmojiASM text (non-empty, starts with expected directives)
  - **Files**: `tests/test_transpiler.py`
  - **Done when**: All function and random tests pass
  - **Verify**: `cd /Users/patrickkavanagh/emojiasm && pytest tests/test_transpiler.py -k "func or random or monte" -v --tb=short`
  - **Commit**: `test(transpiler): add function, random, and integration tests`
  - _Requirements: AC-5.1 through AC-5.4, AC-7.1 through AC-7.5_

- [ ] 3.5 Unit tests for error handling
  - **Do**: Add tests to `tests/test_transpiler.py`:
    - Test unsupported syntax raises `TranspileError` (list comp, class, lambda, try/except, etc.)
    - Test error messages contain line numbers
    - Test error messages contain helpful suggestions
    - Test unsupported import raises with module name
    - Test string literal in expression raises error
    - Test chained comparison raises error with suggestion
    - Test too many arguments to range() raises error
    - Test non-Name for-loop target raises error
  - **Files**: `tests/test_transpiler.py`
  - **Done when**: All error handling tests pass
  - **Verify**: `cd /Users/patrickkavanagh/emojiasm && pytest tests/test_transpiler.py -k "error" -v --tb=short`
  - **Commit**: `test(transpiler): add error handling tests`
  - _Requirements: AC-10.1 through AC-10.3_

## Phase 4: Quality Gates

- [ ] 4.1 Run full test suite
  - **Do**: Run all existing tests plus new transpiler tests to ensure no regressions
  - **Verify**: `cd /Users/patrickkavanagh/emojiasm && pytest -v --tb=short`
  - **Done when**: All tests pass (existing + new)
  - **Commit**: `fix(transpiler): address any test failures` (if needed)

- [ ] 4.2 Create PR and verify CI
  - **Do**: Create a feature branch (if not already on one), push all commits, create PR with:
    - Title: "feat: Python-to-EmojiASM transpiler"
    - Description summarizing the feature, supported Python subset, usage examples
    - Test plan with the Monte Carlo Pi example
  - **Verify**: `gh pr checks --watch` all green
  - **Done when**: PR ready for review with all CI checks passing
  - **Commit**: N/A (PR creation only)

## Notes

- **POC shortcuts taken**: Minimal error messages in Phase 1; no multi-arg print support; no `math.sqrt()`; no `continue` statement; no chained comparisons
- **Production TODOs for Phase 2**: Better error messages; multi-arg print; edge cases; CLI/EmojiASMTool integration
- **Future enhancements** (not in this spec): `continue` statement, chained comparisons, `**` power operator, `math.sqrt()`, string variable support, `while/else` and `for/else`
