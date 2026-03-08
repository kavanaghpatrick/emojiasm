---
spec: python-transpiler
phase: requirements
created: 2026-03-08
generated: auto
---

# Requirements: Python-to-EmojiASM Transpiler

## Summary

Build a transpiler that compiles a numeric subset of Python to EmojiASM `Program` objects via Python's `ast` module, enabling LLM agents to write simple Python functions that run on GPU at scale (10,000 instances for Monte Carlo simulations, parameter sweeps, etc.).

## User Stories

### US-1: Transpile Simple Arithmetic

As an LLM agent, I want to write Python arithmetic expressions (e.g., `x = 3 * (4 + 5)`) and have them compiled to EmojiASM so that I can leverage GPU execution without learning emoji opcodes.

**Acceptance Criteria**:
- AC-1.1: Integer and float literals transpile to `PUSH` instructions
- AC-1.2: Binary operators (`+`, `-`, `*`, `/`, `//`, `%`) transpile to correct EmojiASM opcodes
- AC-1.3: Operator precedence is preserved (parenthesized expressions work correctly)
- AC-1.4: Unary negation (`-x`) transpiles correctly (PUSH 0, compile x, SUB)
- AC-1.5: Python `/` (true division) produces float results even for integer operands

### US-2: Use Variables

As an LLM agent, I want to use Python variables (`x = 5; y = x + 1`) so that I can write readable code with named values.

**Acceptance Criteria**:
- AC-2.1: Variable assignment (`x = expr`) compiles to expression + `STORE` to a unique memory cell
- AC-2.2: Variable read (`x`) compiles to `LOAD` from the assigned memory cell
- AC-2.3: Augmented assignment (`x += 1`, `x *= 2`, etc.) compiles correctly
- AC-2.4: Multiple variables in the same program get distinct memory cells
- AC-2.5: Using an unassigned variable raises a clear transpiler error

### US-3: Control Flow (Conditionals)

As an LLM agent, I want to use `if/elif/else` statements so that I can implement conditional logic.

**Acceptance Criteria**:
- AC-3.1: `if cond: body` transpiles to JZ-based conditional skip
- AC-3.2: `if cond: body else: body` transpiles to JZ + JMP else pattern
- AC-3.3: `if/elif/else` chains transpile correctly with chained labels
- AC-3.4: All comparison operators (`==`, `!=`, `<`, `>`, `<=`, `>=`) work in conditions
- AC-3.5: Boolean operators (`and`, `or`, `not`) work in conditions

### US-4: Control Flow (Loops)

As an LLM agent, I want to use `while` loops and `for i in range(n)` so that I can implement iterative algorithms.

**Acceptance Criteria**:
- AC-4.1: `while cond: body` transpiles to loop with condition check + JZ exit
- AC-4.2: `for i in range(n): body` transpiles to equivalent while loop with counter
- AC-4.3: `for i in range(start, stop): body` works with two-arg range
- AC-4.4: `for i in range(start, stop, step): body` works with three-arg range
- AC-4.5: Nested loops work correctly with independent label sets
- AC-4.6: `break` statement exits the innermost loop

### US-5: Random Number Generation

As an LLM agent, I want to use `random.random()` in my Python code so that I can write Monte Carlo simulations that leverage the GPU's per-thread PRNG.

**Acceptance Criteria**:
- AC-5.1: `import random` is accepted (whitelisted import)
- AC-5.2: `random.random()` compiles to the `RANDOM` opcode
- AC-5.3: Monte Carlo Pi example transpiles and produces correct results
- AC-5.4: Unsupported imports raise a clear error message

### US-6: Print Output

As an LLM agent, I want to use `print()` so that I can output results.

**Acceptance Criteria**:
- AC-6.1: `print(expr)` compiles to expression + `PRINTLN`
- AC-6.2: `print(expr, end="")` compiles to expression + `PRINT` (no newline)
- AC-6.3: `print(a, b, c)` compiles to multiple prints with space separators

### US-7: Function Definitions and Calls

As an LLM agent, I want to define and call simple functions so that I can organize my code.

**Acceptance Criteria**:
- AC-7.1: `def f(x): return x * 2` transpiles to a named function with STORE/LOAD for params
- AC-7.2: `f(5)` transpiles to PUSH args + CALL
- AC-7.3: Return values are passed via stack (top of stack after RET)
- AC-7.4: Functions with multiple parameters work (caller pushes in order, callee STOREs in reverse)
- AC-7.5: Recursive functions work correctly

### US-8: End-to-End GPU Execution

As an LLM agent, I want to call `tool.execute_python(source, n=10000)` so that my Python code is transpiled and run on GPU in one step.

**Acceptance Criteria**:
- AC-8.1: `EmojiASMTool.execute_python()` method accepts Python source and instance count
- AC-8.2: Transpilation + execution completes in a single API call
- AC-8.3: Results include `stats` (mean, std, min, max) for numeric outputs
- AC-8.4: GPU routing works (Tier 1 for numeric-only transpiled programs)

### US-9: CLI Integration

As a developer, I want to run `emojiasm --from-python file.py` so that I can transpile and execute Python files from the command line.

**Acceptance Criteria**:
- AC-9.1: `--from-python file.py` transpiles and runs on VM
- AC-9.2: `--transpile file.py` outputs the generated EmojiASM source text
- AC-9.3: `--from-python file.py --gpu --gpu-instances 1000` transpiles and runs on GPU
- AC-9.4: `--from-python file.py --disasm` shows the generated EmojiASM assembly

### US-10: Error Reporting

As an LLM agent, I want clear error messages when I use unsupported Python features so that I can fix my code.

**Acceptance Criteria**:
- AC-10.1: Unsupported syntax (classes, list comprehensions, etc.) raises `TranspileError` with line number and description
- AC-10.2: Error messages suggest alternatives where possible (e.g., "Use while loop instead of list comprehension")
- AC-10.3: Type errors (string operations in numeric context) caught at transpile time where possible

## Functional Requirements

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-1 | Transpile integer and float literals to PUSH | Must | US-1 |
| FR-2 | Transpile binary arithmetic operators (+, -, *, /, //, %) to stack ops | Must | US-1 |
| FR-3 | Handle operator precedence via AST structure | Must | US-1 |
| FR-4 | Transpile variable assignment to STORE with unique emoji cell | Must | US-2 |
| FR-5 | Transpile variable reads to LOAD | Must | US-2 |
| FR-6 | Transpile augmented assignment (+=, -=, *=, /=, //=, %=) | Must | US-2 |
| FR-7 | Transpile comparison operators to CMP_EQ/CMP_LT/CMP_GT + NOT compositions | Must | US-3 |
| FR-8 | Transpile boolean operators (and, or, not) | Must | US-3 |
| FR-9 | Transpile if/elif/else to label+jump control flow | Must | US-3 |
| FR-10 | Transpile while loops to label+jump loop pattern | Must | US-4 |
| FR-11 | Transpile for-range loops to while-loop equivalents | Should | US-4 |
| FR-12 | Transpile break statements to JMP to loop exit label | Should | US-4 |
| FR-13 | Transpile `random.random()` to RANDOM opcode | Must | US-5 |
| FR-14 | Transpile `print()` to PRINTLN/PRINT | Must | US-6 |
| FR-15 | Transpile function definitions to named EmojiASM functions | Should | US-7 |
| FR-16 | Transpile function calls (push args, CALL, use return value) | Should | US-7 |
| FR-17 | Transpile `return expr` to expr + RET | Should | US-7 |
| FR-18 | Provide `transpile(source) -> Program` entry point | Must | US-8 |
| FR-19 | Provide `transpile_to_source(source) -> str` for debugging | Should | US-9 |
| FR-20 | Add `EmojiASMTool.execute_python()` method | Should | US-8 |
| FR-21 | Add `--from-python` and `--transpile` CLI flags | Should | US-9 |
| FR-22 | Raise `TranspileError` with line number for unsupported syntax | Must | US-10 |
| FR-23 | Python `/` (true division) emits float coercion before DIV | Must | US-1 |
| FR-24 | Whitelist `import random` and `import math` | Must | US-5 |
| FR-25 | Emit HALT at end of main function | Must | US-1 |
| FR-26 | Support `math.sqrt(x)` as `x ** 0.5` equivalent | Could | US-5 |
| FR-27 | Support `**` (power) operator via repeated multiplication or float trick | Could | US-1 |

## Non-Functional Requirements

| ID | Requirement | Category |
|----|-------------|----------|
| NFR-1 | Transpilation completes in < 10ms for programs under 1000 lines | Performance |
| NFR-2 | Generated EmojiASM is Tier 1 (numeric-only) for numeric-only Python input | Performance |
| NFR-3 | Error messages include Python source line number and column | Usability |
| NFR-4 | Zero external dependencies (only stdlib `ast` module) | Maintainability |
| NFR-5 | Transpiler output is deterministic (same input -> same Program) | Correctness |
| NFR-6 | Generated programs pass existing VM and bytecode compiler without errors | Correctness |

## Out of Scope

- Strings beyond simple `print()` arguments (no string variables, concatenation, formatting)
- Lists, dicts, sets, tuples
- Classes and objects
- Exception handling (try/except)
- Generators, comprehensions, lambda
- f-strings, string formatting
- Imports beyond `random` and `math`
- File I/O, network, subprocess
- `continue` statement (V1; can be added later)
- Multiple return values
- Default parameter values
- `*args`, `**kwargs`
- Global/nonlocal declarations
- Decorators

## Dependencies

- Python `ast` module (stdlib, Python 3.10+)
- `emojiasm.parser.Program`, `Function`, `Instruction` dataclasses
- `emojiasm.opcodes.Op` enum
- `emojiasm.disasm.disassemble()` for source text generation
- `emojiasm.inference.EmojiASMTool` for LLM integration
- `emojiasm.__main__` for CLI integration
