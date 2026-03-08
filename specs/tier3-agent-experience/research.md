---
spec: tier3-agent-experience
phase: research
created: 2026-03-08
generated: auto
---

# Research: tier3-agent-experience

## Executive Summary

Tier 3 enhances the LLM agent experience with five features: (1) auto-parallelization wrapper that lets agents write single-instance Python and auto-wraps for N GPU instances, (2) result aggregation builtins (mean, std, median, histogram), (3) numpy-style API shim for common `np.*` calls, (4) better error messages with actionable suggestions, and (5) source maps linking EmojiASM instructions back to Python source lines. All features build on existing transpiler, inference, and GPU infrastructure.

## Codebase Analysis

### Existing Patterns

- **Transpiler** (`emojiasm/transpiler.py`, 1263 lines): Full AST-based Python-to-EmojiASM compiler. Already handles `random.random()`, `random.uniform()`, `random.gauss()` (Box-Muller), `math.*` functions, `for x in range()`, arrays, and function definitions. Error messages use `TranspileError(message, lineno)` with line numbers.
- **Inference tool** (`emojiasm/inference.py`): `EmojiASMTool` with `execute()` (EmojiASM), `execute_python()` (Python via transpiler), `_compute_stats()` (mean, std, min, max, count). Routes to GPU when tier<=2, n>=256.
- **GPU module** (`emojiasm/gpu.py`): `gpu_run()` dispatches N instances via MLX Metal kernel. `_stats()` helper computes mean/std/min/max/count. Tier 1 (numeric-only) and Tier 2 (output buffer) supported.
- **Agent mode** (`emojiasm/agent.py`): `run_agent_mode()` runs N instances on CPU with `ThreadPoolExecutor`. `TracingVM` subclass captures execution traces.
- **CLI** (`emojiasm/__main__.py`): `--from-python`, `--transpile`, `--debug`, `--gpu`, `--gpu-instances` flags exist.
- **Instruction dataclass** (`emojiasm/parser.py`): `Instruction(op, arg, line_num, source)` — `source` field exists but transpiler always sets it to `""`.

### Dependencies

- `ast` module for Python AST parsing (already used by transpiler)
- `statistics` module for median/histogram (stdlib, no new dep)
- Existing `_UNSUPPORTED_SYNTAX` dict in transpiler for error suggestion patterns
- `EmojiASMTool.execute_python()` already does transpile+execute routing

### Constraints

- Transpiler only supports a subset of Python — auto-parallelization must work within this subset
- GPU tier classification (bytecode.py) determines routing — auto-wrapped programs must remain tier 1/2
- `Instruction.source` field exists but is always `""` — needs to be populated by transpiler
- numpy shim must intercept at AST level, before transpilation, to avoid adding numpy as real dependency
- Stats functions currently duplicated in `inference.py._compute_stats()` and `gpu.py._stats()` — should unify

## Feasibility Assessment

| Aspect | Assessment | Notes |
|--------|------------|-------|
| Auto-parallelization | High | Pattern detection via AST analysis; wrap result in HALT (already how GPU instances work) |
| Result aggregation | High | Extend existing `_compute_stats()` with median/histogram; pure Python, no GPU changes needed |
| numpy shim | High | AST rewriting before transpiler visits; map `np.*` calls to existing `math.*`/`random.*` handlers |
| Error messages | High | Extend `_UNSUPPORTED_SYNTAX` dict + add suggestions to `TranspileError` raises throughout |
| Source maps | Medium | Transpiler has `node.lineno` access; need to store Python source lines and add `--debug` output format |

## Recommendations

1. Start with numpy shim (AST rewriting) — most impactful for agent UX, clean layering on existing transpiler
2. Auto-parallelization wrapper is the "killer feature" — detect single-instance pattern, auto-wrap with result-returning HALT
3. Unify stats helpers into a single module before adding median/histogram
4. Source maps need the transpiler to populate `Instruction.source` with Python line text
