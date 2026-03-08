---
spec: tier4-capacity
phase: requirements
created: 2026-03-08
generated: auto
---

# Requirements: tier4-capacity

## Summary

Raise hard capacity limits in the GPU Metal kernel, bytecode compiler, and Python transpiler to support larger, more complex programs. All limits are currently too low for non-trivial transpiled Python with nested loops, many variables, and recursive functions.

## User Stories

### US-1: Transpile programs with many variables
As a developer, I want to transpile Python programs with up to 200 variables so that complex algorithms with nested loops and temporaries don't hit the 50-variable limit.

**Acceptance Criteria**:
- AC-1.1: `EMOJI_POOL` contains at least 200 unique emoji characters
- AC-1.2: No emoji in `EMOJI_POOL` collides with opcodes in `EMOJI_TO_OP` or directives
- AC-1.3: A transpiled program using 100+ variables compiles and runs correctly

### US-2: Transpile programs with many functions
As a developer, I want to define up to 50 functions in transpiled Python so that modular programs with helper functions don't hit the 20-function limit.

**Acceptance Criteria**:
- AC-2.1: `FUNC_EMOJI_POOL` contains at least 50 unique emoji characters
- AC-2.2: No emoji in `FUNC_EMOJI_POOL` collides with variable pool or opcodes
- AC-2.3: A transpiled program with 30+ functions compiles and runs correctly

### US-3: GPU programs with many memory cells
As a developer, I want GPU programs to access up to 128 memory cells so that transpiled programs with many variables execute on GPU without memory cell overflow.

**Acceptance Criteria**:
- AC-3.1: `NUM_MEMORY_CELLS` in `vm.metal` is at least 128
- AC-3.2: STORE/LOAD to cell indices 0-127 work correctly in GPU execution
- AC-3.3: Bytecode operand encoding supports cell indices up to 127

### US-4: Deeper GPU recursion
As a developer, I want GPU programs to recurse up to 32 levels deep so that recursive algorithms like `fib(20)` don't overflow the call stack.

**Acceptance Criteria**:
- AC-4.1: `CALL_STACK_DEPTH` in `vm.metal` is at least 32
- AC-4.2: A recursive function calling 20+ levels deep completes without error on GPU

### US-5: Larger GPU stack
As a developer, I want GPU programs to use a 256-entry stack so that complex expressions and save/restore patterns around recursive calls don't overflow.

**Acceptance Criteria**:
- AC-5.1: `DEFAULT_STACK_DEPTH` in `gpu.py` is at least 256
- AC-5.2: `_GPU_MAX_STACK` in `bytecode.py` matches the new default
- AC-5.3: Stacks buffer in `gpu_run()` is sized correctly for the new depth

## Functional Requirements

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-1 | Expand `EMOJI_POOL` to 200+ emoji | Must | US-1 |
| FR-2 | Expand `FUNC_EMOJI_POOL` to 50+ emoji | Must | US-2 |
| FR-3 | Increase `NUM_MEMORY_CELLS` to 128 | Must | US-3 |
| FR-4 | Increase `CALL_STACK_DEPTH` to 32 | Must | US-4 |
| FR-5 | Increase `DEFAULT_STACK_DEPTH` and `_GPU_MAX_STACK` to 256 | Must | US-5 |
| FR-6 | Ensure no emoji collisions between pools and opcode/directive sets | Must | US-1, US-2 |
| FR-7 | All existing tests continue to pass | Must | All |

## Non-Functional Requirements

| ID | Requirement | Category |
|----|-------------|----------|
| NFR-1 | GPU occupancy should remain above 50% with new limits | Performance |
| NFR-2 | Per-thread memory budget should stay under 10KB | Performance |
| NFR-3 | Emoji pools should use visually distinct, common emoji | Usability |

## Out of Scope

- Runtime-configurable memory cell count (would require kernel recompilation)
- Dynamic memory allocation on GPU
- Expanding CPU VM limits (already at 4096 stack, dict-based memory)
- Array capacity changes (`MAX_ARRAYS`, `MAX_ARRAY_SIZE` in vm.metal)

## Dependencies

- Unicode emoji availability in Python strings
- Metal shader compiler support for larger thread-local arrays
