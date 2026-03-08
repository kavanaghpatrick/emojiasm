---
spec: tier4-capacity
phase: design
created: 2026-03-08
generated: auto
---

# Design: tier4-capacity

## Overview

Increase five hard-coded capacity limits across three layers: Metal kernel constants, Python bytecode compiler caps, and transpiler emoji pools. No architectural changes -- just constant adjustments and expanding string lists.

## Architecture

```
Transpiler (transpiler.py)          Bytecode (bytecode.py)           GPU Kernel (vm.metal)
  EMOJI_POOL: 50 -> 200+             _GPU_MAX_STACK: 128 -> 256       NUM_MEMORY_CELLS: 32 -> 128
  FUNC_EMOJI_POOL: 20 -> 50+                                          CALL_STACK_DEPTH: 16 -> 32
                                    GPU Interface (gpu.py)             stack_depth: 128 -> 256
                                      DEFAULT_STACK_DEPTH: 128 -> 256
```

## Components

### Component A: Metal Kernel Constants (`emojiasm/metal/vm.metal`)
**Purpose**: Define per-thread resource sizes for GPU execution
**Changes**:
- L94: `CALL_STACK_DEPTH` 16 -> 32
- L97: `NUM_MEMORY_CELLS` 32 -> 128

**Impact on thread-local memory**:
- `call_stack[32]`: 32 * 4B = 128B (was 64B)
- `memory[128]`: 128 * 4B = 512B (was 128B)
- Net increase: ~448B per thread (~7KB total with stacks, well within budget per KB #185)

### Component B: Bytecode Compiler Cap (`emojiasm/bytecode.py`)
**Purpose**: Cap static stack analysis for GPU programs
**Changes**:
- L91: `_GPU_MAX_STACK` 128 -> 256

### Component C: GPU Interface Default (`emojiasm/gpu.py`)
**Purpose**: Set default per-instance stack size passed to kernel
**Changes**:
- L23: `DEFAULT_STACK_DEPTH` 128 -> 256

**Impact on device memory**:
- Stacks buffer: `n * 256 * 4B` = 1KB per thread (was 512B)
- For 10K threads: 10MB (was 5MB), well within GPU memory

### Component D: Variable Emoji Pool (`emojiasm/transpiler.py`)
**Purpose**: Map Python variable names to unique emoji memory cell identifiers
**Changes**:
- Expand `EMOJI_POOL` from 50 to 200+ characters
- Use emoji from multiple Unicode blocks: food, animals, objects, nature, sports, vehicles, flags

**Emoji selection criteria**:
1. Must NOT appear in `EMOJI_TO_OP` (opcodes.py)
2. Must NOT appear in directive constants (`DIRECTIVE_FUNC`, `DIRECTIVE_LABEL`, etc.)
3. Must NOT appear in `FUNC_EMOJI_POOL`
4. Should be single-codepoint or stable multi-codepoint sequences
5. Prefer visually distinct emoji

### Component E: Function Emoji Pool (`emojiasm/transpiler.py`)
**Purpose**: Map Python function names to unique emoji identifiers
**Changes**:
- Expand `FUNC_EMOJI_POOL` from 20 to 50+ characters
- Add more colored shapes, symbols, and distinct emoji

**Selection criteria**: Same collision avoidance as Component D, plus must not overlap with `EMOJI_POOL`.

## Data Flow

1. Python source -> Transpiler assigns variables from `EMOJI_POOL` (up to 200+)
2. Transpiler assigns functions from `FUNC_EMOJI_POOL` (up to 50+)
3. Program -> Bytecode compiler maps emoji cells to integer indices 0..N-1
4. Bytecode `_analyze_max_stack_depth()` caps at 256 (was 128)
5. `gpu_run()` allocates stacks buffer with `n * 256` entries
6. Metal kernel uses `memory[128]`, `call_stack[32]`, dynamic `stack_depth=256`

## Technical Decisions

| Decision | Options | Choice | Rationale |
|----------|---------|--------|-----------|
| Memory cells count | 64, 128, 256 | 128 | Matches stack depth; 512B thread-local fits register budget per KB #147 |
| Call stack depth | 24, 32, 64 | 32 | Supports fib(20); 128B minimal overhead |
| Stack depth | 192, 256, 512 | 256 | Per KB #147 max feasible; 1KB device memory per thread |
| Variable pool size | 150, 200, 300 | 200+ | Covers complex programs; more emoji available if needed |
| Function pool size | 40, 50, 80 | 50+ | Covers modular programs; 50 functions is generous |
| Configurability | Constants vs params | Constants (except stack_depth) | Memory cells and call stack are compile-time Metal constants; stack_depth already parameterized |

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `emojiasm/metal/vm.metal` | Modify | Update `CALL_STACK_DEPTH` and `NUM_MEMORY_CELLS` |
| `emojiasm/bytecode.py` | Modify | Update `_GPU_MAX_STACK` |
| `emojiasm/gpu.py` | Modify | Update `DEFAULT_STACK_DEPTH` |
| `emojiasm/transpiler.py` | Modify | Expand `EMOJI_POOL` and `FUNC_EMOJI_POOL` |
| `tests/test_gpu_kernel.py` | Modify | Add/update tests for new limits |
| `tests/test_transpiler.py` | Modify | Add tests for expanded pools |
| `tests/test_emojiasm.py` | No change | Existing tests should pass as-is |

## Error Handling

| Error | Handling | User Impact |
|-------|----------|-------------|
| Variable pool exceeded (>200) | `TranspileError` with count | Same as before, higher limit |
| Function pool exceeded (>50) | `TranspileError` with count | Same as before, higher limit |
| GPU memory cell OOB (>128) | `STATUS_ERROR` in kernel | Same error path, higher limit |
| GPU call stack overflow (>32) | `STATUS_ERROR` in kernel | Same error path, higher limit |
| GPU stack overflow (>256) | `STATUS_ERROR` in kernel | Same error path, higher limit |

## Existing Patterns to Follow

- `vm.metal` L92-97: `constant int` declarations for limits
- `transpiler.py` L35-47: Emoji pools as `list()` of concatenated string literals
- `transpiler.py` L139-141: Pool exhaustion raises `TranspileError`
- `bytecode.py` L91: `_GPU_MAX_STACK` caps analysis
- `gpu.py` L23: `DEFAULT_STACK_DEPTH` constant

## Per-Thread Memory Budget (Updated)

| Resource | Old Size | New Size |
|----------|----------|----------|
| Operand stack (device) | 512B | 1024B |
| Call stack (thread-local) | 64B | 128B |
| Memory cells (thread-local) | 128B | 512B |
| Arrays (thread-local) | 8KB | 8KB (unchanged) |
| PRNG state (thread-local) | 24B | 24B |
| **Total thread-local** | **~8.2KB** | **~8.7KB** |
| **Total with device stack** | **~8.7KB** | **~9.7KB** |

Within 10KB budget per NFR-2. At 9.7KB/thread, 64MB supports ~6,500 concurrent VMs.
