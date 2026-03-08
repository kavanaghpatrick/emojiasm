---
spec: python-transpiler
phase: research
created: 2026-03-08
generated: auto
---

# Research: Python-to-EmojiASM Transpiler

## Executive Summary

Python's `ast` module provides complete, stable AST parsing for all Python syntax. A transpiler targeting the EmojiASM stack-based VM is highly feasible for the numeric subset (arithmetic, variables, loops, conditionals, `random()`). The key challenge is compiling infix expressions to postfix stack operations and mapping Python's structured control flow (if/while/for) to flat label+jump instructions. The existing codebase already has a C AOT compiler (`compiler.py`) that solves the same "traverse Program, emit code" problem, providing a reference pattern.

## Codebase Analysis

### Target Output Format

The transpiler must produce `Program` (from `parser.py`):
- `Program.functions: dict[str, Function]` with `entry_point = "🏠"`
- `Function.instructions: list[Instruction]` with `Function.labels: dict[str, int]`
- `Instruction(op: Op, arg: object, line_num: int, source: str)`

This is identical to what `parse()` returns. All downstream tools (VM, bytecode compiler, GPU pipeline, C compiler, disassembler) accept `Program` directly.

### Existing Patterns to Follow

| Pattern | File | Relevance |
|---------|------|-----------|
| Program/Function/Instruction dataclasses | `parser.py:12-29` | Transpiler output format |
| `compile_to_c()` traverses Program → emits C | `compiler.py:314-365` | Reference for code generation from Program |
| `_uses_strings()` gates numeric-only path | `compiler.py:85-91`, `bytecode.py:108-117` | Transpiler output should be Tier 1 by default |
| `disassemble()` reconstructs source from Program | `disasm.py:7-24` | Can reuse for `transpile_to_source()` |
| `EmojiASMTool.execute()` with GPU/CPU routing | `inference.py:32-85` | Integration point for `execute_python()` |
| CLI with argparse | `__main__.py:16-37` | Add `--from-python`/`--transpile` flags |
| Test pattern: `run()` helper | `tests/test_emojiasm.py:7-11` | Transpiler tests follow same pattern |

### Dependencies

- **Python `ast` module** (stdlib) -- zero external deps needed
- `emojiasm.parser.Program`, `Function`, `Instruction` -- output types
- `emojiasm.opcodes.Op` -- opcode enum
- `emojiasm.disasm.disassemble()` -- for `transpile_to_source()` convenience function

### Key EmojiASM Opcodes for Transpiler

| Python Construct | EmojiASM Opcode(s) | Notes |
|-----------------|---------------------|-------|
| Integer/float literal | `PUSH val` | Direct mapping |
| `x = expr` | `expr` + `STORE cell` | Variable name becomes emoji cell name |
| `x` (read) | `LOAD cell` | |
| `a + b` | `a` `b` `ADD` | Postfix evaluation |
| `a - b` | `a` `b` `SUB` | |
| `a * b` | `a` `b` `MUL` | |
| `a / b` | `a` `b` `DIV` | Python `/` is float div; EmojiASM `DIV` is `//` for int operands |
| `a // b` | `a` `b` `DIV` | Floor div matches directly |
| `a % b` | `a` `b` `MOD` | |
| `a == b` | `a` `b` `CMP_EQ` | |
| `a != b` | `a` `b` `CMP_EQ` `NOT` | No native != |
| `a < b` | `a` `b` `CMP_LT` | |
| `a > b` | `a` `b` `CMP_GT` | |
| `a <= b` | `a` `b` `CMP_GT` `NOT` | `not (a > b)` |
| `a >= b` | `a` `b` `CMP_LT` `NOT` | `not (a < b)` |
| `a and b` | `a` `b` `AND` | |
| `a or b` | `a` `b` `OR` | |
| `not a` | `a` `NOT` | |
| `if cond:` | `cond` `JZ else_label` body `JMP end_label` `else_label:` | |
| `while cond:` | `loop_label:` `cond` `JZ end_label` body `JMP loop_label` `end_label:` | |
| `for i in range(n):` | Init counter, while loop pattern | Sugar over while loop |
| `random.random()` | `RANDOM` | Direct opcode |
| `print(x)` | `x` `PRINTLN` | |
| `def f(x):` | `📜 f` body `RET` | Params via stack convention |
| `f(x)` | `x` `CALL f` | Push args, call |
| `return x` | `x` `RET` | Leave on stack |

### Constraints

1. **Variable naming**: EmojiASM memory cells are emoji strings. Python variable names must be mapped to unique emoji identifiers. Strategy: use a deterministic mapping (e.g., `x` -> `🅰️`, `y` -> `🅱️`, etc.) or generate unique emoji names.

2. **Division semantics mismatch**: Python `/` is always float division, EmojiASM `DIV` is `//` for int operands. For true Python `/` semantics, need to ensure at least one operand is float (e.g., multiply by `1.0` first or cast).

3. **No native `!=`, `<=`, `>=`**: Must compose from `CMP_EQ`+`NOT`, `CMP_GT`+`NOT`, `CMP_LT`+`NOT`.

4. **Label generation**: Need unique label names for control flow. Use emoji+counter scheme (e.g., `🏷️1`, `🏷️2`).

5. **Function arguments**: EmojiASM functions share a global stack. Arguments are passed via stack (caller pushes, callee pops into named cells). No formal parameter syntax.

6. **Scope**: Python has function-local scope. EmojiASM memory cells are global. Must handle carefully (or document limitation).

7. **`for range()`**: Must decompose into while loop with counter variable.

8. **Augmented assignment**: `x += 1` -> `LOAD x`, `PUSH 1`, `ADD`, `STORE x`.

## Python `ast` Module Analysis

### Relevant AST Nodes

| Node Type | Fields | Transpiler Handling |
|-----------|--------|---------------------|
| `ast.Module` | `body: list[stmt]` | Top-level container |
| `ast.FunctionDef` | `name, args, body` | Map to `📜 name` |
| `ast.Return` | `value` | Compile value, emit `RET` |
| `ast.Assign` | `targets, value` | Compile value, `STORE` for each target |
| `ast.AugAssign` | `target, op, value` | `LOAD` + compile value + op + `STORE` |
| `ast.If` | `test, body, orelse` | Labels + conditional jumps |
| `ast.While` | `test, body` | Loop labels + conditional jumps |
| `ast.For` | `target, iter, body` | Decompose `range()` into while |
| `ast.Expr` | `value` | Expression statement (e.g., `print()`) |
| `ast.BinOp` | `left, op, right` | Compile left, right, emit op |
| `ast.UnaryOp` | `op, operand` | Compile operand, emit op |
| `ast.BoolOp` | `op, values` | Chain with AND/OR |
| `ast.Compare` | `left, ops, comparators` | Handle chained comparisons |
| `ast.Call` | `func, args` | Detect `print()`, `random.random()`, user funcs |
| `ast.Name` | `id` | Variable reference |
| `ast.Constant` | `value` | Literal int/float |
| `ast.Import` | `names` | Whitelist `random`, `math` |

### ast.NodeVisitor Pattern

The standard approach is `ast.NodeVisitor` or `ast.NodeTransformer`:

```python
class EmojiASMCompiler(ast.NodeVisitor):
    def visit_BinOp(self, node):
        self.visit(node.left)   # pushes left operand
        self.visit(node.right)  # pushes right operand
        self._emit(OP_MAP[type(node.op)])  # emits operation
```

This naturally produces postfix (stack-based) code by visiting children before emitting the operation.

## Similar Projects / Prior Art

| Project | Approach | Relevance |
|---------|----------|-----------|
| `py2many` | Python AST -> multiple targets | General AST-to-target pattern |
| `Brython` | Python -> JS via AST | AST visitor code generation |
| `Cython` | Python -> C via AST | Similar numeric focus |
| `numba` | Python -> LLVM IR via AST | Numeric-only subset inspiration |
| CPython compiler | `ast` -> bytecode (dis module) | Stack-based code generation reference |
| Forth compilers | Infix-to-postfix | Direct analog for stack machine targeting |

CPython's own compiler (in `Python/compile.c`) is the closest analog: it compiles `ast` nodes to stack-based bytecode. The key techniques (expression flattening, label-based control flow) are directly applicable.

## Feasibility Assessment

| Aspect | Assessment | Notes |
|--------|------------|-------|
| Technical Viability | **High** | Python ast is well-suited; EmojiASM opcodes cover the needed operations |
| Effort Estimate | **M** (Medium) | ~15-20 tasks; core expression compilation is straightforward, control flow slightly more complex |
| Risk Level | **Low** | No external deps; well-understood compilation techniques; existing test infrastructure |
| Performance | **High** | AST parsing + code gen is O(n) in source size; easily < 10ms for typical programs |
| GPU Compatibility | **High** | Numeric Python subset maps to Tier 1 (numeric-only) programs by default |

### Key Risks

1. **Division semantics**: Python `/` vs EmojiASM `DIV` floor division for ints. Mitigation: for Python `/`, ensure float coercion by pushing `1.0` and multiplying if needed.
2. **Variable scope**: EmojiASM globals vs Python locals. Mitigation: document as limitation for V1; each function gets unique emoji prefix for its locals.
3. **Chained comparisons**: `a < b < c` is common in Python. Mitigation: decompose to `(a < b) and (b < c)`, but need to DUP `b`.

## Recommendations

1. **Start with expression compilation** -- most value, simplest to test, enables the Monte Carlo use case
2. **Use emoji variable pool** -- pre-assign variable names to emoji cells from a deterministic pool
3. **Follow `ast.NodeVisitor` pattern** -- standard, well-documented, matches the recursive nature of AST
4. **Emit `Program` directly** -- not source text; source text comes via `disassemble()` for debugging
5. **Division**: Use `1.0 *` coercion for Python `/` to force float division semantics
6. **Test against VM** -- each transpiler feature gets a test that transpiles Python, runs on VM, checks output
