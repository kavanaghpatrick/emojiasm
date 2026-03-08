---
spec: tier1-numeric-ops
phase: requirements
created: 2026-03-08
generated: auto
---

# Requirements: tier1-numeric-ops

## Summary

Add 9 new numeric opcodes (POW, SQRT, SIN, COS, EXP, LOG, ABS, MIN, MAX), transpiler support for `math.*` functions/constants, `random.uniform`/`random.gauss`, and chained comparisons. All opcodes wired through full pipeline: opcodes, parser, VM, bytecode, Metal kernel, GPU glue, C compiler, disassembler.

## User Stories

### US-1: Power operator
As a transpiler user, I want to write `x ** 2` in Python and have it compile to a POW opcode so that exponentiation works natively.

**Acceptance Criteria**:
- AC-1.1: `print(2 ** 10)` transpiles and outputs `1024`
- AC-1.2: `print(4 ** 0.5)` transpiles and outputs `2.0`
- AC-1.3: POW opcode works in direct EmojiASM (`📥 2 📥 10 🔋 🖨️`) and outputs `1024`
- AC-1.4: POW compiles through bytecode, Metal kernel, and C compiler

### US-2: Math module functions
As a transpiler user, I want to call `math.sqrt(x)`, `math.sin(x)`, `math.cos(x)`, `math.exp(x)`, `math.log(x)`, `abs(x)`, `min(a,b)`, `max(a,b)` and have them compile to dedicated opcodes.

**Acceptance Criteria**:
- AC-2.1: `math.sqrt(16)` outputs `4.0`
- AC-2.2: `math.sin(0)` outputs `0.0`
- AC-2.3: `math.cos(0)` outputs `1.0`
- AC-2.4: `math.exp(0)` outputs `1.0`
- AC-2.5: `math.log(1)` outputs `0.0`
- AC-2.6: `abs(-5)` outputs `5`
- AC-2.7: `min(3, 7)` outputs `3`
- AC-2.8: `max(3, 7)` outputs `7`
- AC-2.9: All 8 opcodes work in direct EmojiASM with their assigned emoji
- AC-2.10: All 8 opcodes compile through bytecode, Metal kernel, and C compiler

### US-3: Math constants
As a transpiler user, I want `math.pi` and `math.e` to resolve to their numeric values.

**Acceptance Criteria**:
- AC-3.1: `print(math.pi)` outputs `3.141592653589793`
- AC-3.2: `print(math.e)` outputs `2.718281828459045`
- AC-3.3: Constants usable in expressions: `print(math.pi * 2)` outputs correct value

### US-4: Random distribution functions
As a transpiler user, I want `random.uniform(a, b)` and `random.gauss(mu, sigma)` to compile correctly.

**Acceptance Criteria**:
- AC-4.1: `random.uniform(1, 10)` returns a value in [1, 10)
- AC-4.2: `random.gauss(0, 1)` returns a float (standard normal sample)
- AC-4.3: Both work on CPU (VM) and GPU (Metal kernel)
- AC-4.4: Implemented via inline expansion using existing opcodes (RANDOM, PUSH, MUL, ADD, SQRT, LOG, COS, SIN)

### US-5: Chained comparisons
As a transpiler user, I want `a < b < c` to compile correctly instead of raising an error.

**Acceptance Criteria**:
- AC-5.1: `print(1 < 2 < 3)` outputs `1`
- AC-5.2: `print(1 < 3 < 2)` outputs `0`
- AC-5.3: `print(1 < 2 < 3 < 4)` outputs `1` (3+ comparisons)
- AC-5.4: Mixed comparison ops work: `print(1 <= 2 < 3)` outputs `1`
- AC-5.5: Works in if conditions: `if 0 < x < 10:` compiles correctly

## Functional Requirements

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-1 | Add POW opcode (emoji, enum, VM, bytecode, Metal, C compiler) | Must | US-1 |
| FR-2 | Add SQRT opcode through full pipeline | Must | US-2 |
| FR-3 | Add SIN opcode through full pipeline | Must | US-2 |
| FR-4 | Add COS opcode through full pipeline | Must | US-2 |
| FR-5 | Add EXP opcode through full pipeline | Must | US-2 |
| FR-6 | Add LOG opcode through full pipeline | Must | US-2 |
| FR-7 | Add ABS opcode through full pipeline | Must | US-2 |
| FR-8 | Add MIN opcode through full pipeline | Must | US-2 |
| FR-9 | Add MAX opcode through full pipeline | Must | US-2 |
| FR-10 | Transpiler: `ast.Pow` -> POW opcode | Must | US-1 |
| FR-11 | Transpiler: `math.sqrt/sin/cos/exp/log` -> opcodes | Must | US-2 |
| FR-12 | Transpiler: `abs()` builtin -> ABS opcode | Must | US-2 |
| FR-13 | Transpiler: `min(a,b)` and `max(a,b)` builtins -> opcodes | Must | US-2 |
| FR-14 | Transpiler: `math.pi` -> PUSH 3.141592653589793 | Must | US-3 |
| FR-15 | Transpiler: `math.e` -> PUSH 2.718281828459045 | Must | US-3 |
| FR-16 | Transpiler: `random.uniform(a,b)` inline expansion | Should | US-4 |
| FR-17 | Transpiler: `random.gauss(mu,sigma)` inline expansion | Should | US-4 |
| FR-18 | Transpiler: chained comparisons support | Must | US-5 |
| FR-19 | C compiler preamble adds `#include <math.h>` | Must | FR-1..9 |
| FR-20 | Update `_uses_strings()` to NOT flag new math ops as string-using | Must | FR-1..9 |
| FR-21 | Update `_STACK_EFFECTS` in bytecode.py for new opcodes | Must | FR-1..9 |
| FR-22 | Update `docs/REFERENCE.md` with new opcodes | Should | US-1,2 |

## Non-Functional Requirements

| ID | Requirement | Category |
|----|-------------|----------|
| NFR-1 | All existing 448+ tests continue to pass | Regression |
| NFR-2 | GPU opcode validation (`validate_opcodes()`) passes with new ops | Consistency |
| NFR-3 | MSL math functions use float precision (consistent with GPU numeric path) | Precision |
| NFR-4 | C compiler math functions use double precision (consistent with existing numeric path) | Precision |

## Out of Scope

- New opcodes for `random.randint`, `random.choice`, `random.shuffle`
- Bitwise operators (AND, OR, XOR, SHIFT)
- Complex number support
- `math.floor`, `math.ceil`, `math.round` (can be added later)
- String math (e.g., repeating strings with `*`)
- `from math import sqrt` style direct function import

## Dependencies

- Existing opcode pipeline (opcodes.py, vm.py, bytecode.py, vm.metal, gpu.py, compiler.py, disasm.py)
- C compiler requires `<math.h>` and `-lm` flag on Linux (macOS links math automatically)
- MSL `<metal_stdlib>` already included in vm.metal
