---
spec: tier3-agent-experience
phase: requirements
created: 2026-03-08
generated: auto
---

# Requirements: tier3-agent-experience

## Summary

Enhance the LLM agent experience for EmojiASM by enabling agents to write simple single-instance Python that auto-parallelizes across GPU instances, adding numpy-style API shims, richer result aggregation, better error messages with suggestions, and source maps for transpiler debugging.

## User Stories

### US-1: Auto-parallelization wrapper
As an LLM agent, I want to write single-instance Python (e.g., a Monte Carlo sample) and have it automatically parallelized across N GPU instances so that I don't need to understand the GPU dispatch model.

**Acceptance Criteria**:
- AC-1.1: `execute_python(source, n=10000)` accepts single-instance Python that uses `random`, returns a numeric result, and auto-wraps it for N parallel instances
- AC-1.2: Detection of single-instance pattern: no explicit loops over large ranges (range(N) where N > threshold), uses `random`, produces a result value
- AC-1.3: Each instance runs independently with its own PRNG seed
- AC-1.4: Results array has one float per instance, suitable for statistical aggregation

### US-2: Result aggregation builtins
As an LLM agent, I want richer statistics on multi-instance results so that I get actionable numeric insights from parallel runs.

**Acceptance Criteria**:
- AC-2.1: Stats include `mean`, `std`, `min`, `max`, `count`, `median`
- AC-2.2: `histogram(bins=N)` returns bin edges and counts for the results array
- AC-2.3: Stats are computed consistently across CPU and GPU execution paths
- AC-2.4: Existing `_compute_stats()` and `_stats()` are unified into a single implementation

### US-3: numpy-style API shim
As an LLM agent, I want to write `np.random.random()`, `np.sqrt()`, `np.pi`, etc. and have the transpiler accept them so that I can use familiar numpy idioms.

**Acceptance Criteria**:
- AC-3.1: `import numpy as np` is accepted by the transpiler
- AC-3.2: `np.random.random()` maps to `RANDOM` opcode
- AC-3.3: `np.random.normal(mu, sigma)` maps to Box-Muller transform (existing `random.gauss` path)
- AC-3.4: `np.random.uniform(a, b)` maps to `RANDOM * (b-a) + a` (existing `random.uniform` path)
- AC-3.5: `np.sqrt(x)`, `np.abs(x)`, `np.sin(x)`, `np.cos(x)`, `np.exp(x)`, `np.log(x)` map to corresponding opcodes
- AC-3.6: `np.pi` maps to `PUSH 3.141592653589793`
- AC-3.7: Unsupported numpy calls (e.g., `np.array()`, `np.linalg.*`) produce clear error messages with alternatives

### US-4: Better error messages with suggestions
As an LLM agent, I want transpiler errors to suggest EmojiASM-compatible alternatives so that I can self-correct without human intervention.

**Acceptance Criteria**:
- AC-4.1: `x = [1,2,3]` error suggests "Use `arr = [0.0] * N` for fixed-size arrays"
- AC-4.2: `for x in items:` error suggests "Only `for x in range(N)` is supported"
- AC-4.3: `import numpy` error suggests "Use `import random` + `import math` instead"
- AC-4.4: Unsupported function calls suggest the closest supported alternative
- AC-4.5: All error messages include the offending line number

### US-5: Source maps for debugging
As an LLM agent, I want to see which Python source line produced each EmojiASM instruction so that I can understand and debug transpilation.

**Acceptance Criteria**:
- AC-5.1: Transpiler populates `Instruction.source` with the Python source line text
- AC-5.2: `--from-python --debug` shows Python line -> EmojiASM instruction mapping on stderr
- AC-5.3: Source map info is available programmatically via the `Program` object
- AC-5.4: `execute_python()` can optionally return source map data in its result dict

## Functional Requirements

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-1 | Auto-detect single-instance Python pattern via AST analysis | Must | US-1 |
| FR-2 | Auto-wrap single-instance source to return result per instance | Must | US-1 |
| FR-3 | Add `median` to stats output | Must | US-2 |
| FR-4 | Add `histogram(bins=N)` to stats output | Should | US-2 |
| FR-5 | Unify `_compute_stats()` and `_stats()` into single module | Must | US-2 |
| FR-6 | Accept `import numpy as np` in transpiler | Must | US-3 |
| FR-7 | Map `np.random.*`, `np.sqrt`, `np.abs`, `np.pi` etc. to existing opcodes | Must | US-3 |
| FR-8 | Add actionable suggestions to transpiler error messages | Must | US-4 |
| FR-9 | Populate `Instruction.source` with Python source line text | Must | US-5 |
| FR-10 | Add source map debug output mode for `--from-python --debug` | Should | US-5 |

## Non-Functional Requirements

| ID | Requirement | Category |
|----|-------------|----------|
| NFR-1 | Auto-parallelization detection must complete in <10ms for typical programs | Performance |
| NFR-2 | numpy shim adds zero runtime overhead (pure AST rewriting) | Performance |
| NFR-3 | Error messages must be machine-parseable (consistent format with line numbers) | Usability |

## Out of Scope

- Full numpy ndarray support (vectorized operations, broadcasting, slicing)
- `np.linalg.*`, `np.fft.*`, or other numpy submodules beyond `np.random` and top-level math
- Auto-parallelization of programs with complex control flow (nested loops, recursion)
- GPU kernel changes for source map storage
- Interactive debugging / step-through mode

## Dependencies

- Existing transpiler AST infrastructure
- Existing `EmojiASMTool.execute_python()` routing
- Existing `random.uniform()`, `random.gauss()` Box-Muller in transpiler
- Python `statistics` stdlib module (for median)
