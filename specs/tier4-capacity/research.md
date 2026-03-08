---
spec: tier4-capacity
phase: research
created: 2026-03-08
generated: auto
---

# Research: tier4-capacity

## Executive Summary

Raising capacity limits across the GPU kernel, transpiler pools, and bytecode module. All changes are low-risk constant/pool adjustments. The main trade-off is GPU occupancy vs capacity -- KB #147 confirms 256-entry stack is feasible, and KB #185 shows ~6.5KB/thread budget supports ~10K concurrent VMs.

## Codebase Analysis

### Current Limits (Exact Locations)

| Limit | Current | File | Line |
|-------|---------|------|------|
| GPU memory cells | 32 | `emojiasm/metal/vm.metal` | L97 `NUM_MEMORY_CELLS = 32` |
| GPU call stack depth | 16 | `emojiasm/metal/vm.metal` | L94 `CALL_STACK_DEPTH = 16` |
| GPU stack depth | 128 | `emojiasm/gpu.py` | L23 `DEFAULT_STACK_DEPTH = 128` |
| GPU stack cap (bytecode) | 128 | `emojiasm/bytecode.py` | L91 `_GPU_MAX_STACK = 128` |
| Variable emoji pool | 50 | `emojiasm/transpiler.py` | L35-41 `EMOJI_POOL` |
| Function emoji pool | 20 | `emojiasm/transpiler.py` | L44-47 `FUNC_EMOJI_POOL` |
| CPU VM max_stack | 4096 | `emojiasm/vm.py` | L21 `stack_size=4096` |

### Existing Patterns

- `vm.metal` uses `constant int` declarations for compile-time limits (L94, L97)
- `gpu.py` passes `stack_depth` as a kernel parameter (already configurable per-dispatch)
- `bytecode.py` caps `_analyze_max_stack_depth()` at `_GPU_MAX_STACK`
- `transpiler.py` `VarManager` raises `TranspileError` when pool exhausted (L139-141)
- `FUNC_EMOJI_POOL` checked at L544-545 during function registration

### Dependencies

- MLX `mx.fast.metal_kernel()` -- stacks buffer sized as `n * stack_depth`
- Metal compiler -- `constant int` values baked into kernel at compile time
- `_split_kernel_source()` in `gpu.py` -- patches scalar refs to pointer derefs
- Tests: `test_gpu_kernel.py` (source checks), `test_transpiler.py` (transpile+run)

### Constraints

- Metal thread-local arrays: larger `memory[]` and `call_stack[]` consume more registers, reducing occupancy
- KB #147: 256-entry stack feasible, 64-entry thread-private arrays start impacting occupancy
- KB #185: ~6.5KB/thread budget at current sizes; doubling stack+memory stays under ~8KB
- 24-bit operand field in bytecode: max 16M memory cells (not a concern at 128)
- `EMOJI_POOL` must avoid collisions with opcodes (`EMOJI_TO_OP`) and directives

## Feasibility Assessment

| Aspect | Assessment | Notes |
|--------|------------|-------|
| Technical Viability | High | Pure constant changes + expanding string lists |
| Effort Estimate | S | ~2-3 hours including tests |
| Risk Level | Low | No architectural changes; only raising limits |

## Recommendations

1. Increase `NUM_MEMORY_CELLS` to 128 (matches stack depth, 512B thread-local)
2. Increase `CALL_STACK_DEPTH` to 32 (supports `fib(20)` and deeper recursion)
3. Increase `DEFAULT_STACK_DEPTH` and `_GPU_MAX_STACK` to 256 (per KB #147)
4. Expand `EMOJI_POOL` to 200+ using Unicode emoji blocks (animals, food, objects, symbols)
5. Expand `FUNC_EMOJI_POOL` to 50+ using colored shapes, hearts, flags
6. Keep limits as constants (not runtime-configurable) for simplicity; `stack_depth` already parameterized
