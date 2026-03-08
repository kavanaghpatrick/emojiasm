---
spec: tier2-arrays
phase: tasks
total_tasks: 18
created: 2026-03-08
generated: auto
---

# Tasks: tier2-arrays

## Phase 1: Make It Work (POC)

Focus: Get arrays working end-to-end in VM + transpiler. Skip GPU/compiler, accept hardcoded values.

- [x] 1.1 Add array opcodes to Op enum and emoji mappings
  - **Do**: Add ALLOC, ALOAD, ASTORE, ALEN to `Op` IntEnum in opcodes.py. Add emoji mappings: `🗃️` -> ALLOC, `📖` -> ALOAD, `✏️` -> ASTORE, `🧮` -> ALEN. Add variation selectors if needed (check if `✏️`/`✏` differ). Add all 4 to `OPS_WITH_ARG`.
  - **Files**: `emojiasm/opcodes.py`
  - **Done when**: `from emojiasm.opcodes import Op; assert Op.ALLOC.value > 0`
  - **Verify**: `python3 -c "from emojiasm.opcodes import Op; print(Op.ALLOC, Op.ALOAD, Op.ASTORE, Op.ALEN)"`
  - **Commit**: `feat(opcodes): add ALLOC, ALOAD, ASTORE, ALEN array opcodes`
  - _Requirements: FR-1, FR-2_
  - _Design: Component A_

- [x] 1.2 Implement array opcodes in VM
  - **Do**: Add 4 new `case Op.X:` branches in `_exec_function` match statement. ALLOC: `size = self._pop(); self.memory[arg] = [0.0] * int(size)`. ALOAD: `idx = self._pop(); arr = self.memory[arg]; self._push(arr[int(idx)])`. ASTORE: `val = self._pop(); idx = self._pop(); arr = self.memory[arg]; arr[int(idx)] = val`. ALEN: `self._push(len(self.memory[arg]))`. Add bounds checking and type checking (verify cell is a list). Raise VMError with descriptive messages.
  - **Files**: `emojiasm/vm.py`
  - **Done when**: VM can execute handwritten EmojiASM programs with arrays
  - **Verify**: `python3 -c "from emojiasm.parser import parse; from emojiasm.vm import VM; p = parse('📜 🏠\n  📥 3\n  🗃️ 🅰️\n  📥 0\n  📥 42\n  ✏️ 🅰️\n  📥 0\n  📖 🅰️\n  🖨️\n  🛑'); out = VM(p).run(); assert '42' in ''.join(out); print('OK')"`
  - **Commit**: `feat(vm): implement ALLOC, ALOAD, ASTORE, ALEN execution`
  - _Requirements: FR-3, FR-4, FR-5, FR-6, FR-7_
  - _Design: Component B_

- [x] 1.3 Add basic array tests
  - **Do**: Add tests in test_emojiasm.py: test_array_alloc_and_store, test_array_load, test_array_len, test_array_bounds_error, test_array_non_array_error. Use raw EmojiASM source via `run()` helper.
  - **Files**: `tests/test_emojiasm.py`
  - **Done when**: All new tests pass
  - **Verify**: `pytest tests/test_emojiasm.py -k array -v`
  - **Commit**: `test(vm): add array opcode tests`
  - _Requirements: AC-1.1 through AC-1.5_
  - _Design: Component B_

- [x] 1.4 Transpiler: array allocation and access
  - **Do**: In transpiler.py: (1) Extend VarManager to track array vs scalar variables (add `_array_vars: set[str]`). (2) Handle `visit_Assign` for `ast.BinOp(ast.List, ast.Mult, ast.Constant)` pattern -- detect `[0.0] * N`, emit PUSH N + ALLOC cell, mark var as array. (3) Add `visit_Subscript` for read access: emit visit(index), ALOAD cell. (4) Modify `visit_Assign` to detect `ast.Subscript` as target: emit visit(index), visit(value), ASTORE cell. (5) Handle `visit_AugAssign` with Subscript target: emit visit(index), DUP, ALOAD cell, visit(value), OP, ASTORE cell.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: Python array programs transpile and run correctly
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.vm import VM; p = transpile('arr = [0.0] * 5\narr[0] = 42\nprint(arr[0])'); out = VM(p).run(); assert '42' in ''.join(out); print('OK')"`
  - **Commit**: `feat(transpiler): compile array allocation and subscript access`
  - _Requirements: FR-8, FR-9, FR-10_
  - _Design: Component H_

- [x] 1.5 Transpiler: sum() and len() builtins
  - **Do**: In transpiler.py `visit_Call`: (1) Handle `len(var)` when var is known array -> emit ALEN cell. (2) Handle `sum(var)` when var is known array -> emit inline accumulation loop: PUSH 0.0, allocate temp_i cell, PUSH 0, STORE temp_i, loop: LOAD temp_i, ALEN cell, CMP_LT, JZ end, LOAD temp_i, ALOAD cell, ADD, LOAD temp_i, PUSH 1, ADD, STORE temp_i, JMP loop, end label.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `sum()` and `len()` work on array variables
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.vm import VM; p = transpile('arr = [0.0] * 3\narr[0] = 1\narr[1] = 2\narr[2] = 3\nprint(sum(arr))\nprint(len(arr))'); out = VM(p).run(); text = ''.join(out); assert '6' in text and '3' in text; print('OK')"`
  - **Commit**: `feat(transpiler): add sum() and len() builtins for arrays`
  - _Requirements: FR-11, FR-12_
  - _Design: Component H_

- [x] 1.6 Transpiler: constant folding
  - **Do**: In `visit_BinOp`: before visiting children, check if both `node.left` and `node.right` are `ast.Constant` with numeric values. If so, evaluate at compile time and emit single PUSH. Handle Add, Sub, Mult, Div, FloorDiv, Mod, Pow. Guard against division by zero (don't fold, let runtime handle). Also add identity elimination: check if one side is Constant(0) for add/sub or Constant(1) for mul/div and skip the no-op.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `4.0 * 3.14159` emits 1 instruction instead of 3
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.disasm import disassemble; p = transpile('x = 4.0 * 3.14159\nprint(x)'); d = disassemble(p); print(d); assert d.count('📥') == 1; print('OK: only 1 PUSH')"`
  - **Commit**: `feat(transpiler): add constant folding for compile-time expressions`
  - _Requirements: FR-13, FR-14_
  - _Design: Component I_

- [x] 1.7 Transpiler: type inference for division coercion
  - **Do**: Add type tracking to VarManager: `_types: dict[str, str]` mapping var name to `"int"`, `"float"`, or `"unknown"`. Update on assignment (Constant int -> "int", Constant float -> "float", BinOp with any float operand -> "float", etc.). In `visit_BinOp` for `ast.Div`: check if left operand is a Name with known float type. If yes, skip `PUSH 1.0, MUL` coercion.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `x = 1.0; y = x / 2` skips float coercion
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.disasm import disassemble; p = transpile('x = 1.0\ny = x / 2\nprint(y)'); d = disassemble(p); print(d); assert '📥 1.0\n  ✖' not in d or d.count('📥 1.0') == 1; print('OK')"`
  - **Commit**: `feat(transpiler): add type inference to skip unnecessary float coercion`
  - _Requirements: FR-15, FR-16_
  - _Design: Component J_

- [x] 1.8 POC Checkpoint
  - **Do**: Run full test suite. Verify arrays work end-to-end via transpiler + VM. Run existing tests to confirm no regressions.
  - **Done when**: All existing tests pass + new array tests pass
  - **Verify**: `pytest`
  - **Commit**: `feat(tier2): complete POC for arrays, builtins, constant folding, type inference`

## Phase 2: Refactoring

After POC validated, extend to all backends.

- [x] 2.1 Bytecode encoder: add array opcode support
  - **Do**: In bytecode.py: (1) Add to `OP_MAP`: `Op.ALLOC: 0x42, Op.ALOAD: 0x43, Op.ASTORE: 0x44, Op.ALEN: 0x45`. (2) Add to `_STACK_EFFECTS`: ALLOC=-1, ALOAD=0, ASTORE=-2, ALEN=+1. (3) Encoding uses same `_build_memory_map` for cell ID in operand. (4) ALLOC/ALOAD/ASTORE/ALEN handled in `compile_to_bytecode` same as STORE/LOAD (mem_map lookup).
  - **Files**: `emojiasm/bytecode.py`
  - **Done when**: Programs with arrays compile to bytecode without errors
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.bytecode import compile_to_bytecode; p = transpile('arr = [0.0] * 5\narr[0] = 42\nprint(arr[0])'); gp = compile_to_bytecode(p); print(f'bytecode: {len(gp.bytecode)} instructions, tier {gp.gpu_tier}'); print('OK')"`
  - **Commit**: `feat(bytecode): add ALLOC, ALOAD, ASTORE, ALEN GPU opcodes`
  - _Requirements: FR-17_
  - _Design: Component D_

- [x] 2.2 GPU interface: update opcode maps
  - **Do**: In gpu.py: (1) Add to `GPU_OPCODES`: `"ALLOC": 0x42, "ALOAD": 0x43, "ASTORE": 0x44, "ALEN": 0x45`. (2) Run `validate_opcodes()` to verify consistency.
  - **Files**: `emojiasm/gpu.py`
  - **Done when**: `validate_opcodes()` passes with new array opcodes
  - **Verify**: `python3 -c "from emojiasm.gpu import validate_opcodes; validate_opcodes(); print('OK')"`
  - **Commit**: `feat(gpu): add array opcodes to GPU opcode map`
  - _Requirements: FR-17_
  - _Design: Component F_

- [x] 2.3 Metal kernel: add array storage and opcode handling
  - **Do**: In vm.metal: (1) Add constants `MAX_ARRAYS = 8`, `MAX_ARRAY_SIZE = 256`. (2) Add opcode constants `OP_ALLOC = 0x42`, `OP_ALOAD = 0x43`, `OP_ASTORE = 0x44`, `OP_ALEN = 0x45`. (3) Add per-thread arrays: `float arrays[MAX_ARRAYS][MAX_ARRAY_SIZE]; int array_sizes[MAX_ARRAYS];` with zero initialization. (4) Add 4 switch cases: ALLOC (pop size, set array_sizes, zero-fill), ALOAD (pop index, bounds check, push), ASTORE (pop value+index, bounds check, store), ALEN (push size).
  - **Files**: `emojiasm/metal/vm.metal`
  - **Done when**: Metal kernel compiles with new opcodes (validated by GPU tests if MLX available)
  - **Verify**: `python3 -c "from emojiasm.gpu import get_kernel_source; src = get_kernel_source(); assert 'OP_ALLOC' in src; assert 'OP_ALOAD' in src; print('OK')"`
  - **Commit**: `feat(metal): add array storage and ALLOC/ALOAD/ASTORE/ALEN opcodes`
  - _Requirements: FR-18_
  - _Design: Component E_

- [x] 2.4 C compiler: add array opcode emission
  - **Do**: In compiler.py: (1) Scan for ALLOC/ALOAD/ASTORE/ALEN ops to collect array cells (separate from scalar mem map). (2) Emit C array declarations: `static double _arr0[256]; static int _arr0_sz = 0;` for numeric, `static Val _arr0[256]; static int _arr0_sz = 0;` for mixed. (3) Add _emit_inst cases for each: ALLOC -> set size + memset, ALOAD -> index + push, ASTORE -> pop value + index + store, ALEN -> push size. (4) Include `<string.h>` for memset if not already included.
  - **Files**: `emojiasm/compiler.py`
  - **Done when**: Programs with arrays compile to C and produce correct output
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; from emojiasm.compiler import compile_to_c; p = transpile('arr = [0.0] * 5\narr[0] = 42\nprint(arr[0])'); c = compile_to_c(p); assert '_arr' in c; print('OK')"`
  - **Commit**: `feat(compiler): add C emission for ALLOC/ALOAD/ASTORE/ALEN`
  - _Requirements: FR-19_
  - _Design: Component G_

- [x] 2.5 Add error handling for edge cases
  - **Do**: Ensure all backends handle: (1) ALLOC with size 0 or negative (VM: error, GPU: status error). (2) ALOAD/ASTORE on uninitialized cell (VM: VMError). (3) ALOAD/ASTORE on scalar cell (VM: VMError). (4) Index out of bounds with clear error message showing index and array size. (5) GPU: array cell ID >= MAX_ARRAYS -> status error. (6) GPU: size > MAX_ARRAY_SIZE -> status error.
  - **Files**: `emojiasm/vm.py`, `emojiasm/metal/vm.metal`
  - **Done when**: All error cases produce clear messages or status codes
  - **Verify**: `pytest tests/test_emojiasm.py -k "array" -v`
  - **Commit**: `refactor(vm): add comprehensive array error handling`
  - _Design: Error Handling_

## Phase 3: Testing

- [x] 3.1 Comprehensive VM array tests
  - **Do**: Add tests for: multi-element arrays, store/load round-trip, ALEN correctness, overwrite existing elements, multiple arrays, array in function calls, array with loop (for i in range: arr[i] = i*i), sum() and len() builtins, constant folding verification (instruction count), type inference (check coercion skipped).
  - **Files**: `tests/test_emojiasm.py`
  - **Done when**: Full coverage of array operations via raw EmojiASM
  - **Verify**: `pytest tests/test_emojiasm.py -k array -v`
  - **Commit**: `test(vm): comprehensive array operation tests`
  - _Requirements: AC-1.1 through AC-1.5_

- [x] 3.2 Transpiler tests for arrays and optimizations
  - **Do**: Add tests in test_transpiler.py (or test_emojiasm.py if no separate file): transpile array allocation, subscript read/write, augmented assignment on subscript, sum()/len(), constant folding (verify instruction count reduced), type inference (verify no unnecessary PUSH 1.0 MUL in division), edge cases (nested subscript error, non-array subscript error).
  - **Files**: `tests/test_transpiler.py` or `tests/test_emojiasm.py`
  - **Done when**: All transpiler array and optimization tests pass
  - **Verify**: `pytest -k "transpil" -v`
  - **Commit**: `test(transpiler): add tests for arrays, constant folding, type inference`
  - _Requirements: AC-2.1 through AC-5.4_

- [x] 3.3 Bytecode and compiler tests
  - **Do**: Add tests for: bytecode encoding of array opcodes (verify packed uint32 values), C compiler output contains array declarations and access code, compiled C program produces correct output when run. If test infrastructure for C compilation exists, add to it.
  - **Files**: `tests/test_bytecode.py` or `tests/test_emojiasm.py`
  - **Done when**: Bytecode encoding and C compilation of array programs verified
  - **Verify**: `pytest -k "bytecode or compiler" -v`
  - **Commit**: `test(bytecode,compiler): add array opcode encoding and compilation tests`
  - _Requirements: AC-6.4, AC-7.1 through AC-7.4_

## Phase 4: Quality Gates

- [x] 4.1 Local quality check
  - **Do**: Run full test suite, type check (if configured), lint. Verify all 448+ existing tests still pass. Run example programs to validate no regressions.
  - **Verify**: `pytest && python3 -m emojiasm examples/hello.emoji && python3 -m emojiasm examples/fibonacci.emoji`
  - **Done when**: All commands pass with zero failures
  - **Commit**: `fix(tier2): address lint/type issues` (if needed)

- [ ] 4.2 Create PR and verify CI
  - **Do**: Push branch, create PR with `gh pr create` describing all 4 features (arrays, sum/len, constant folding, type inference). Link to issue #28.
  - **Verify**: `gh pr checks --watch` all green
  - **Done when**: PR ready for review with all CI checks passing

## Notes

- **POC shortcuts taken**: GPU/Metal and C compiler deferred to Phase 2. Type inference starts simple (variable-level, not expression-level).
- **Production TODOs**: GPU memory budget validation (8 arrays x 256 floats = 8KB per thread), performance benchmarks for constant folding impact.
- **ASTORE stack order**: `( index value -- )` means index is pushed first, then value. This maps naturally to `arr[i] = expr` where index is evaluated before the expression.
- **Emoji choices**: `🗃️` (card file box) for ALLOC, `📖` (open book) for ALOAD, `✏️` (pencil) for ASTORE, `🧮` (abacus) for ALEN. Check for variation selector variants.
