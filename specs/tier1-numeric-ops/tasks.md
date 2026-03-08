---
spec: tier1-numeric-ops
phase: tasks
total_tasks: 18
created: 2026-03-08
generated: auto
---

# Tasks: tier1-numeric-ops

## Phase 1: Make It Work (POC)

Focus: Get all 9 opcodes working end-to-end through opcodes + VM + basic tests. Skip bytecode/Metal/compiler until POC validated.

- [x] 1.1 Add 9 new Op enum values and emoji mappings to opcodes.py
  - **Do**: Add `POW = auto()`, `SQRT = auto()`, `SIN = auto()`, `COS = auto()`, `EXP = auto()`, `LOG = auto()`, `ABS = auto()`, `MIN = auto()`, `MAX = auto()` after `RANDOM = auto()` in Op IntEnum. Add emoji mappings to EMOJI_TO_OP: `"🔋": Op.POW`, `"🌱": Op.SQRT`, `"📈": Op.SIN`, `"📉": Op.COS`, `"🚀": Op.EXP`, `"📓": Op.LOG`, `"💪": Op.ABS`, `"⬇️": Op.MIN`, `"⬇": Op.MIN`, `"⬆️": Op.MAX`, `"⬆": Op.MAX`. Ensure multi-codepoint emoji (with variation selectors ⬇️/⬆️) are listed BEFORE their bare versions (⬇/⬆) in the dict for correct prefix matching.
  - **Files**: `emojiasm/opcodes.py`
  - **Done when**: `from emojiasm.opcodes import Op; print(Op.POW, Op.SQRT, Op.MAX)` works, and `EMOJI_TO_OP["🔋"] == Op.POW`
  - **Verify**: `python3 -c "from emojiasm.opcodes import Op, EMOJI_TO_OP; assert EMOJI_TO_OP['🔋'] == Op.POW; assert EMOJI_TO_OP['⬆️'] == Op.MAX; assert EMOJI_TO_OP['⬆'] == Op.MAX; print('OK')"`
  - **Commit**: `feat(opcodes): add POW SQRT SIN COS EXP LOG ABS MIN MAX opcodes`
  - _Requirements: FR-1 through FR-9_
  - _Design: Component 1_

- [x] 1.2 Add VM execution for all 9 new opcodes
  - **Do**: Add `import math` at top of vm.py (after existing imports). Add 9 new match/case arms after the `case Op.RANDOM:` block. Binary ops (POW, MIN, MAX): `b, a = self._pop(), self._pop()` then push result. Unary ops (SQRT, SIN, COS, EXP, LOG, ABS): `a = self._pop()` then push result. For SQRT: wrap in try/except ValueError for negative input, raise VMError. For LOG: wrap in try/except for domain errors. ABS uses builtin `abs()`, not `math.fabs()` to preserve int type.
  - **Files**: `emojiasm/vm.py`
  - **Done when**: All 9 opcodes execute correctly in the VM
  - **Verify**: `python3 -c "from emojiasm.parser import parse; from emojiasm.vm import VM; p=parse('📥 2\n📥 10\n🔋\n🖨️\n🛑'); print(''.join(VM(p).run()))"`  should output `1024`
  - **Commit**: `feat(vm): add dispatch for POW SQRT SIN COS EXP LOG ABS MIN MAX`
  - _Requirements: FR-1 through FR-9_
  - _Design: Component 2_

- [x] 1.3 Add basic EmojiASM tests for all 9 new opcodes
  - **Do**: Add tests to `tests/test_emojiasm.py` using the existing `run()` helper. Test each opcode: POW (`📥 2 📥 10 🔋` -> 1024), SQRT (`📥 16 🌱` -> 4.0), SIN (`📥 0 📈` -> 0.0), COS (`📥 0 📉` -> 1.0), EXP (`📥 0 🚀` -> 1.0), LOG (`📥 1 📓` -> 0.0), ABS (`📥 -5 💪` -> 5 preserving int), MIN (`📥 3 📥 7 ⬇️` -> 3), MAX (`📥 3 📥 7 ⬆️` -> 7). Also test float precision: `SQRT(2)` ~= 1.4142, `SIN(math.pi/2)` ~= 1.0.
  - **Files**: `tests/test_emojiasm.py`
  - **Done when**: All new tests pass with `pytest tests/test_emojiasm.py -v`
  - **Verify**: `pytest tests/test_emojiasm.py -v --tb=short`
  - **Commit**: `test(vm): add tests for new math opcodes`
  - _Requirements: AC-1.3, AC-2.9_
  - _Design: Component 2_

- [x] 1.4 Add transpiler support for `**` operator and math functions
  - **Do**: In `transpiler.py`: (1) Replace the `ast.Pow` error in `visit_BinOp` with `self.visit(left); self.visit(right); self._emit(Op.POW)`. Add `ast.Pow: Op.POW` to `_BINOP_MAP` and `_AUGOP_MAP`. (2) In `visit_Call`, add handler for `math.*` attribute calls (sqrt, sin, cos, exp, log) mapping to corresponding opcodes. (3) Add handler for `abs(x)` -> ABS, `min(a,b)` -> MIN, `max(a,b)` -> MAX builtins. (4) Update `visit_Attribute` to handle `math.pi` -> PUSH 3.141592653589793 and `math.e` -> PUSH 2.718281828459045. Must handle the case where math.pi/math.e appear in expressions (not just as standalone calls).
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("import math\nprint(2 ** 10)")` produces a working program, `transpile("import math\nprint(math.sqrt(16))")` works
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.vm import VM; p=transpile('print(2**10)'); print(''.join(VM(p).run()))"`
  - **Commit**: `feat(transpiler): add power operator and math function support`
  - _Requirements: FR-10 through FR-15_
  - _Design: Component 7a, 7b, 7c, 7d_

- [x] 1.5 Add transpiler support for chained comparisons
  - **Do**: In `visit_Compare`, replace the `len(node.ops) > 1` error. Extract comparison emission to `_emit_cmp_op(self, cmp_op, node)` helper. For chained comparisons `a op1 b op2 c ...`: visit left, then for each (op, comparator): visit comparator, if not last: DUP + ROT, emit comparison, if i > 0: AND, if not last: SWAP. Handle all comparison types: Lt, Gt, LtE, GtE, Eq, NotEq. LtE and GtE use CMP_GT+NOT and CMP_LT+NOT respectively (existing pattern).
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `print(1 < 2 < 3)` transpiles and outputs `1`, `print(1 < 3 < 2)` outputs `0`
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.vm import VM; p=transpile('print(1 < 2 < 3)'); print(''.join(VM(p).run()))"`
  - **Commit**: `feat(transpiler): support chained comparisons`
  - _Requirements: FR-18_
  - _Design: Component 7f_

- [x] 1.6 Add transpiler support for random.uniform and random.gauss
  - **Do**: In `visit_Call`, add handlers for `random.uniform(a, b)` and `random.gauss(mu, sigma)`. uniform: inline as `a + (b-a) * random()` — visit args[0], visit args[1], visit args[0] again, SUB, RANDOM, MUL, ADD. gauss: Box-Muller inline — RANDOM, LOG, PUSH -2.0, MUL, SQRT, RANDOM, PUSH 2*pi, MUL, COS, MUL, then visit sigma, MUL, visit mu, ADD. Both require `"random" in self._imports`.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `random.uniform(1, 10)` transpiles and outputs a value in [1, 10)
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.vm import VM; p=transpile('import random\nx = random.uniform(1, 10)\nprint(x)'); out=''.join(VM(p).run()); v=float(out.strip()); assert 1<=v<10, f'got {v}'; print('OK', v)"`
  - **Commit**: `feat(transpiler): add random.uniform and random.gauss`
  - _Requirements: FR-16, FR-17_
  - _Design: Component 7e_

- [x] 1.7 Add transpiler tests for all new features
  - **Do**: Add tests to `tests/test_transpiler.py` using the existing `run_py()` helper. Test classes: `TestPower` (2**10=1024, 4**0.5=2.0, x**=2 augmented assign), `TestMathFunctions` (sqrt(16)=4.0, sin(0)=0.0, cos(0)=1.0, exp(0)=1.0, log(1)=0.0, abs(-5)=5, min(3,7)=3, max(3,7)=7), `TestMathConstants` (math.pi ~= 3.14159, math.e ~= 2.71828, math.pi*2 expression), `TestChainedComparisons` (1<2<3=1, 1<3<2=0, 1<2<3<4=1, mixed ops 1<=2<3=1, in if condition), `TestRandomDistributions` (uniform in range, gauss returns float). Use approximate assertions for float comparisons.
  - **Files**: `tests/test_transpiler.py`
  - **Done when**: All new tests pass
  - **Verify**: `pytest tests/test_transpiler.py -v --tb=short`
  - **Commit**: `test(transpiler): add tests for math ops, constants, chained cmp, random`
  - _Requirements: AC-1.1 through AC-5.5_
  - _Design: Component 7_

- [x] 1.8 POC Checkpoint — verify all features work end-to-end on VM
  - **Do**: Run full test suite. Verify all existing tests still pass (regression). Verify all new tests pass. Run a combined example: `import math; print(math.sqrt(2**10)); print(math.sin(math.pi/2)); print(1 < 2 < 3)`
  - **Done when**: All tests pass, combined example works
  - **Verify**: `pytest --tb=short -q`
  - **Commit**: `feat(tier1): complete POC for numeric ops`

## Phase 2: Full Pipeline (Bytecode + Metal + C Compiler)

- [x] 2.1 Add bytecode encoding for 9 new opcodes
  - **Do**: In `bytecode.py`: Add 9 entries to `OP_MAP` (POW=0x15 through MAX=0x1D). Add 9 entries to `_STACK_EFFECTS` (POW=-1, SQRT/SIN/COS/EXP/LOG/ABS=0, MIN=-1, MAX=-1). The `_uses_strings()` function doesn't need changes since new ops are not string ops.
  - **Files**: `emojiasm/bytecode.py`
  - **Done when**: `compile_to_bytecode(parse("📥 2 📥 10 🔋 🛑"))` succeeds without BytecodeError
  - **Verify**: `python3 -c "from emojiasm.bytecode import compile_to_bytecode; from emojiasm.parser import parse; g=compile_to_bytecode(parse('📥 2\n📥 10\n🔋\n🛑')); print('bytecode len:', len(g.bytecode), 'tier:', g.gpu_tier)"`
  - **Commit**: `feat(bytecode): add encoding for math opcodes`
  - _Requirements: FR-1 through FR-9, FR-21_
  - _Design: Component 3_

- [x] 2.2 Add Metal kernel dispatch for 9 new opcodes
  - **Do**: In `metal/vm.metal`: Add 9 opcode constants after `OP_RANDOM` (OP_POW=0x15 through OP_MAX=0x1D). Add 9 switch cases in the dispatch loop. Binary ops (POW, MIN, MAX) follow OP_MUL pattern: check sp<2, decrement sp, apply MSL function. Unary ops (SQRT, SIN, COS, EXP, LOG, ABS) follow OP_NOT pattern: check sp<1, apply MSL function in-place. MSL functions: `pow()`, `sqrt()`, `sin()`, `cos()`, `exp()`, `log()`, `abs()` (or `fabs()`), `min()`, `max()`.
  - **Files**: `emojiasm/metal/vm.metal`
  - **Done when**: Metal shader compiles without errors (validated by gpu.py tests)
  - **Verify**: `python3 -c "from emojiasm.gpu import get_kernel_source; src=get_kernel_source(); assert 'OP_POW' in src; assert 'OP_MAX' in src; print('OK')"`
  - **Commit**: `feat(metal): add GPU dispatch for math opcodes`
  - _Requirements: FR-1 through FR-9_
  - _Design: Component 4_

- [ ] 2.3 Add GPU glue entries for 9 new opcodes
  - **Do**: In `gpu.py`: Add 9 entries to `GPU_OPCODES` dict matching bytecode OP_MAP values exactly. No `_GPU_NAME_TO_OP_NAME` changes needed since GPU names match Op enum names directly.
  - **Files**: `emojiasm/gpu.py`
  - **Done when**: `validate_opcodes()` passes with new opcodes
  - **Verify**: `python3 -c "from emojiasm.gpu import validate_opcodes; validate_opcodes(); print('OK')"`
  - **Commit**: `feat(gpu): add GPU_OPCODES entries for math ops`
  - _Requirements: NFR-2_
  - _Design: Component 5_

- [ ] 2.4 Add C compiler emission for 9 new opcodes
  - **Do**: In `compiler.py`: (1) Add `#include <math.h>` to both `_PREAMBLE_NUMERIC` and `_PREAMBLE_MIXED` after the existing `#include <time.h>`. (2) Add 9 `elif op == Op.X:` blocks in `_emit_inst` after the `Op.RANDOM` block. Each block handles both numeric_only and mixed mode. Binary ops: `{ double b=POP(),a=POP(); PUSH_N(func(a,b)); }`. Unary ops: `{ double a=POP(); PUSH_N(func(a)); }`. C functions: `pow()`, `sqrt()`, `sin()`, `cos()`, `exp()`, `log()`, `fabs()` (not abs which is int-only in C), `fmin()`, `fmax()`.
  - **Files**: `emojiasm/compiler.py`
  - **Done when**: `compile_to_c(parse("📥 2 📥 10 🔋 🖨️ 🛑"))` generates valid C with `pow()` call
  - **Verify**: `python3 -c "from emojiasm.compiler import compile_to_c; from emojiasm.parser import parse; c=compile_to_c(parse('📥 2\n📥 10\n🔋\n🖨️\n🛑')); assert 'pow(' in c; assert 'math.h' in c; print('OK')"`
  - **Commit**: `feat(compiler): add C emission for math opcodes`
  - _Requirements: FR-19_
  - _Design: Component 6_

- [ ] 2.5 Add bytecode and GPU tests for new opcodes
  - **Do**: In `tests/test_bytecode.py`: Add tests verifying OP_MAP contains all 9 new ops, bytecode encoding roundtrips correctly, stack effects are defined for all new ops, gpu_tier classification is still correct for programs using new ops. In `tests/test_gpu_kernel.py`: Add tests verifying Metal kernel source contains all new opcode constants and switch cases. Test `validate_opcodes()` passes.
  - **Files**: `tests/test_bytecode.py`, `tests/test_gpu_kernel.py`
  - **Done when**: New tests pass
  - **Verify**: `pytest tests/test_bytecode.py tests/test_gpu_kernel.py -v --tb=short`
  - **Commit**: `test(bytecode,gpu): add tests for math opcode encoding`
  - _Requirements: NFR-2_
  - _Design: Components 3, 4, 5_

## Phase 3: Documentation and Polish

- [ ] 3.1 Update docs/REFERENCE.md with new opcodes
  - **Do**: Add a new "Math" section to the Instruction Set in REFERENCE.md between Arithmetic and Comparison. Include all 9 opcodes with emoji, name, stack effect, and notes. Update the "Python Transpiler" section to list new supported features: `**`, `math.sqrt/sin/cos/exp/log`, `abs()`, `min()`, `max()`, `math.pi`, `math.e`, `random.uniform()`, `random.gauss()`, chained comparisons. Update the "Not supported" line to remove `**`.
  - **Files**: `docs/REFERENCE.md`
  - **Done when**: Reference doc accurately describes all new features
  - **Verify**: `grep -c "POW\|SQRT\|SIN\|COS\|EXP\|LOG\|ABS\|MIN\|MAX" docs/REFERENCE.md` returns >= 9
  - **Commit**: `docs: add math opcodes to language reference`
  - _Requirements: FR-22_
  - _Design: N/A_

- [ ] 3.2 Add example program using new math ops
  - **Do**: Create `examples/math_functions.emoji` demonstrating all 9 new opcodes. Include: power (2^10), sqrt(16), sin/cos of pi/4, exp(1), log(e), abs(-42), min/max of pairs. Print results with labels using PRINTS+ADD pattern.
  - **Files**: `examples/math_functions.emoji`
  - **Done when**: `emojiasm examples/math_functions.emoji` runs and produces correct output
  - **Verify**: `python3 -m emojiasm examples/math_functions.emoji`
  - **Commit**: `docs: add math_functions.emoji example`
  - _Design: N/A_

## Phase 4: Quality Gates

- [ ] 4.1 Full regression test suite
  - **Do**: Run complete test suite including all existing and new tests. Verify all 448+ existing tests still pass. Run type checking if available.
  - **Verify**: `pytest --tb=short -q`
  - **Done when**: All tests pass, zero failures
  - **Commit**: `fix(tier1): address any remaining issues` (if needed)

- [ ] 4.2 Create PR and verify CI
  - **Do**: Push branch, create PR with `gh pr create` summarizing: 9 new math opcodes (POW, SQRT, SIN, COS, EXP, LOG, ABS, MIN, MAX) wired through full pipeline (opcodes, VM, bytecode, Metal kernel, GPU glue, C compiler), transpiler support for `**`, `math.*` functions, `math.pi`/`math.e` constants, `random.uniform`/`random.gauss`, chained comparisons. Reference issue #27. Include test counts.
  - **Verify**: `gh pr checks --watch` all green
  - **Done when**: PR ready for review
  - **Commit**: N/A (PR creation, not a commit)

## Notes

- **POC shortcuts taken**: Bytecode, Metal, and C compiler deferred to Phase 2; Phase 1 validates VM correctness only
- **Production TODOs in Phase 2**: Add `#include <math.h>` to C preamble, ensure `-lm` linker flag on Linux
- **Emoji ordering matters**: Multi-codepoint emoji with variation selectors (⬇️/⬆️) must precede bare versions (⬇/⬆) in EMOJI_TO_OP dict for correct prefix matching (KB #13, #21)
- **Float precision**: GPU uses float32, CPU uses float64. Math function results may differ slightly between GPU and CPU paths. Tests should use approximate comparisons where needed.
- **Disassembler**: No changes needed — `OP_TO_EMOJI` reverse map automatically picks up new entries
