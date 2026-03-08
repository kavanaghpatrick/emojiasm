---
spec: tier4-capacity
phase: tasks
total_tasks: 12
created: 2026-03-08
generated: auto
---

# Tasks: tier4-capacity

## Phase 1: Make It Work (POC)

Focus: Change all constants and expand pools. Verify existing tests still pass.

- [x] 1.1 Increase GPU memory cells from 32 to 128
  - **Do**: In `emojiasm/metal/vm.metal`, change `constant int NUM_MEMORY_CELLS = 32;` to `constant int NUM_MEMORY_CELLS = 128;`
  - **Files**: `emojiasm/metal/vm.metal`
  - **Done when**: The constant reads 128; no other code changes needed since all usage is via `NUM_MEMORY_CELLS`
  - **Verify**: `grep "NUM_MEMORY_CELLS = 128" emojiasm/metal/vm.metal`
  - **Commit**: `feat(gpu): increase memory cells from 32 to 128`
  - _Requirements: FR-3_
  - _Design: Component A_

- [x] 1.2 Increase GPU call stack depth from 16 to 32
  - **Do**: In `emojiasm/metal/vm.metal`, change `constant int CALL_STACK_DEPTH = 16;` to `constant int CALL_STACK_DEPTH = 32;`
  - **Files**: `emojiasm/metal/vm.metal`
  - **Done when**: The constant reads 32
  - **Verify**: `grep "CALL_STACK_DEPTH = 32" emojiasm/metal/vm.metal`
  - **Commit**: `feat(gpu): increase call stack depth from 16 to 32`
  - _Requirements: FR-4_
  - _Design: Component A_

- [x] 1.3 Increase GPU stack depth from 128 to 256
  - **Do**:
    1. In `emojiasm/gpu.py`, change `DEFAULT_STACK_DEPTH = 128` to `DEFAULT_STACK_DEPTH = 256`
    2. In `emojiasm/bytecode.py`, change `_GPU_MAX_STACK = 128` to `_GPU_MAX_STACK = 256`
  - **Files**: `emojiasm/gpu.py`, `emojiasm/bytecode.py`
  - **Done when**: Both constants read 256
  - **Verify**: `grep "DEFAULT_STACK_DEPTH = 256" emojiasm/gpu.py && grep "_GPU_MAX_STACK = 256" emojiasm/bytecode.py`
  - **Commit**: `feat(gpu): increase stack depth from 128 to 256`
  - _Requirements: FR-5_
  - _Design: Components B, C_

- [ ] 1.4 Expand variable emoji pool from 50 to 200+
  - **Do**: In `emojiasm/transpiler.py`, replace `EMOJI_POOL` with an expanded list of 200+ emoji. Use emoji from these Unicode blocks: food/drink, animals, nature, sports, vehicles, objects, symbols. Verify no collisions with `EMOJI_TO_OP` keys or directive constants by running the collision check script. Keep the existing 50 emoji as the first 50 entries (preserves backward compatibility for any serialized programs).
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `len(EMOJI_POOL) >= 200` and no collision with opcodes/directives
  - **Verify**: `python3 -c "from emojiasm.transpiler import EMOJI_POOL; from emojiasm.opcodes import EMOJI_TO_OP; print(f'Pool size: {len(EMOJI_POOL)}'); assert len(EMOJI_POOL) >= 200; assert len(set(EMOJI_POOL)) == len(EMOJI_POOL), 'duplicates'; collisions = [e for e in EMOJI_POOL if e in EMOJI_TO_OP]; print(f'Opcode collisions: {len(collisions)} (ok if used only as memory cell names)')"`
  - **Commit**: `feat(transpiler): expand variable emoji pool to 200+`
  - _Requirements: FR-1, FR-6_
  - _Design: Component D_

- [ ] 1.5 Expand function emoji pool from 20 to 50+
  - **Do**: In `emojiasm/transpiler.py`, replace `FUNC_EMOJI_POOL` with an expanded list of 50+ emoji. Use colored circles, squares, diamonds, and other shape/symbol emoji. Ensure no overlap with `EMOJI_POOL`, `EMOJI_TO_OP`, or directives.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `len(FUNC_EMOJI_POOL) >= 50` and no collision with variable pool or opcodes
  - **Verify**: `python3 -c "from emojiasm.transpiler import EMOJI_POOL, FUNC_EMOJI_POOL; from emojiasm.opcodes import EMOJI_TO_OP; print(f'Func pool: {len(FUNC_EMOJI_POOL)}'); assert len(FUNC_EMOJI_POOL) >= 50; assert len(set(FUNC_EMOJI_POOL)) == len(FUNC_EMOJI_POOL), 'duplicates'; assert not set(FUNC_EMOJI_POOL) & set(EMOJI_POOL), 'cross-collision with var pool'"`
  - **Commit**: `feat(transpiler): expand function emoji pool to 50+`
  - _Requirements: FR-2, FR-6_
  - _Design: Component E_

- [ ] 1.6 POC Checkpoint -- verify all existing tests pass
  - **Do**: Run the full test suite to ensure no regressions from constant changes and pool expansion
  - **Done when**: All tests pass (pytest exit code 0)
  - **Verify**: `pytest`
  - **Commit**: `feat(tier4): complete POC for capacity limit increases`

## Phase 2: Refactoring

- [ ] 2.1 Update docstrings and comments for new limits
  - **Do**:
    1. In `emojiasm/transpiler.py`, update the comment `# Emoji pool for variable memory cells (50 characters)` to reflect new count
    2. Update the comment `# Emoji pool for function names` similarly
    3. In `emojiasm/bytecode.py`, update the docstring mentioning "Max stack depth capped at 128"
    4. In `emojiasm/metal/vm.metal`, update any comments referencing old limit values
  - **Files**: `emojiasm/transpiler.py`, `emojiasm/bytecode.py`, `emojiasm/metal/vm.metal`
  - **Done when**: All comments/docstrings reference correct new values
  - **Verify**: `grep -n "50 characters\|capped at 128\|32 cells\|16 entries" emojiasm/transpiler.py emojiasm/bytecode.py emojiasm/metal/vm.metal` should return no hits
  - **Commit**: `docs: update comments for new capacity limits`
  - _Design: All components_

- [ ] 2.2 Add collision validation utility
  - **Do**: Add a `_validate_emoji_pools()` function in `transpiler.py` that checks for collisions between `EMOJI_POOL`, `FUNC_EMOJI_POOL`, and `EMOJI_TO_OP`/directives. Call it at module load (once) and raise `RuntimeError` if collisions found that would cause parsing ambiguity. Note: collisions with opcodes used only as memory cell names (STORE/LOAD args) are acceptable since the parser distinguishes these contexts.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: Function exists and runs at import time without error
  - **Verify**: `python3 -c "import emojiasm.transpiler; print('Import OK, no collisions')"`
  - **Commit**: `refactor(transpiler): add emoji pool collision validation`
  - _Design: Component D, E_

## Phase 3: Testing

- [ ] 3.1 Test expanded variable pool limits
  - **Do**: Add test in `tests/test_transpiler.py`:
    1. `test_many_variables`: Transpile+run a program that uses 100+ unique variables with assignments and reads
    2. `test_variable_pool_size`: Assert `len(EMOJI_POOL) >= 200`
    3. `test_variable_pool_no_duplicates`: Assert all entries unique
  - **Files**: `tests/test_transpiler.py`
  - **Done when**: New tests pass
  - **Verify**: `pytest tests/test_transpiler.py -k "many_variables or variable_pool" -v`
  - **Commit**: `test(transpiler): add tests for expanded variable pool`
  - _Requirements: AC-1.1, AC-1.2, AC-1.3_

- [ ] 3.2 Test expanded function pool and GPU kernel limits
  - **Do**: Add tests:
    1. In `tests/test_transpiler.py`: `test_many_functions` -- transpile+run a program with 30+ `def` statements
    2. In `tests/test_transpiler.py`: `test_function_pool_size` -- assert `len(FUNC_EMOJI_POOL) >= 50`
    3. In `tests/test_gpu_kernel.py`: `test_memory_cells_128` -- verify kernel source has `NUM_MEMORY_CELLS = 128`
    4. In `tests/test_gpu_kernel.py`: `test_call_stack_depth_32` -- verify kernel source has `CALL_STACK_DEPTH = 32`
    5. In `tests/test_gpu_kernel.py`: `test_default_stack_depth_256` -- verify `DEFAULT_STACK_DEPTH == 256`
  - **Files**: `tests/test_transpiler.py`, `tests/test_gpu_kernel.py`
  - **Done when**: All new tests pass
  - **Verify**: `pytest tests/test_transpiler.py tests/test_gpu_kernel.py -k "many_functions or function_pool or memory_cells_128 or call_stack_depth_32 or stack_depth_256" -v`
  - **Commit**: `test: add tests for expanded pools and GPU limits`
  - _Requirements: AC-2.1, AC-2.3, AC-3.1, AC-4.1, AC-5.1_

## Phase 4: Quality Gates

- [ ] 4.1 Local quality check
  - **Do**: Run all quality checks:
    1. `pytest` -- full test suite
    2. `python3 -m py_compile emojiasm/transpiler.py` -- syntax check
    3. `python3 -m py_compile emojiasm/gpu.py` -- syntax check
    4. `python3 -m py_compile emojiasm/bytecode.py` -- syntax check
  - **Verify**: All commands exit 0
  - **Done when**: All quality checks pass
  - **Commit**: `fix(tier4): address any lint/type issues` (if needed)

- [ ] 4.2 Create PR and verify CI
  - **Do**: Push branch, create PR with `gh pr create` referencing issue #30
  - **Verify**: `gh pr checks --watch` all green
  - **Done when**: PR ready for review

## Notes

- **POC shortcuts taken**: No configurability for memory cells or call stack (compile-time Metal constants); collision validation deferred to Phase 2
- **Existing collisions**: `EMOJI_POOL` already has `🔢` (MOD opcode) and `📊` (DATA directive) -- these work fine because they're used as STORE/LOAD arguments, not parsed as opcodes
- **Production TODOs**: Consider making memory cell count a kernel parameter (requires kernel recompilation) in future iteration
