---
spec: tier3-agent-experience
phase: tasks
total_tasks: 16
created: 2026-03-08
generated: auto
---

# Tasks: tier3-agent-experience

## Phase 1: Make It Work (POC)

Focus: Get each feature working end-to-end. Skip edge cases, accept minimal implementations.

- [x] 1.1 Create unified stats module
  - **Do**: Create `emojiasm/stats.py` with `compute_stats(values, histogram_bins=10)` function. Return dict with `mean`, `std`, `min`, `max`, `count`, `median`, `histogram` (dict with `edges` and `counts` lists). Use `statistics.median` from stdlib. Histogram: compute bin edges from min to max, count values in each bin.
  - **Files**: `emojiasm/stats.py`
  - **Done when**: `compute_stats([1,2,3,4,5])` returns dict with all 7 keys, median=3, histogram has edges and counts
  - **Verify**: `python3 -c "from emojiasm.stats import compute_stats; r = compute_stats([1,2,3,4,5]); print(r); assert r['median'] == 3; assert 'histogram' in r"`
  - **Commit**: `feat(stats): add unified stats module with median and histogram`
  - _Requirements: FR-3, FR-4, FR-5_
  - _Design: Component C_

- [ ] 1.2 Wire unified stats into inference.py and gpu.py
  - **Do**: Replace `EmojiASMTool._compute_stats()` in `inference.py` with import from `emojiasm.stats.compute_stats`. Replace `_stats()` in `gpu.py` with import from `emojiasm.stats.compute_stats`. Ensure both callers pass `histogram_bins=0` to skip histogram when not needed (backward compat).
  - **Files**: `emojiasm/inference.py`, `emojiasm/gpu.py`
  - **Done when**: All existing tests pass with unified stats
  - **Verify**: `pytest tests/ -x -q`
  - **Commit**: `refactor(stats): unify stats computation in inference and gpu modules`
  - _Requirements: FR-5_
  - _Design: Component C_

- [ ] 1.3 Add numpy shim AST rewriter
  - **Do**: Add `_rewrite_numpy(tree: ast.Module) -> ast.Module` function in `transpiler.py`. Detect `import numpy as np` (track alias). Walk AST with `ast.NodeTransformer` subclass: rewrite `np.random.random()` -> `random.random()`, `np.random.normal(mu, sigma)` -> `random.gauss(mu, sigma)`, `np.random.uniform(a,b)` -> `random.uniform(a,b)`, `np.sqrt(x)` -> `math.sqrt(x)`, `np.abs(x)` -> `abs(x)`, `np.sin/cos/exp/log(x)` -> `math.sin/cos/exp/log(x)`, `np.pi` -> `math.pi`. Add `import random` and `import math` nodes if not present. Update `visit_Import`/`visit_ImportFrom` to accept `numpy`. Call `_rewrite_numpy` in `transpile()` after `ast.parse()`.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("import numpy as np\nx = np.random.random()\nresult = np.sqrt(x)")` produces valid Program
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; p = transpile('import numpy as np\nx = np.random.random()\nresult = np.sqrt(x)'); print('OK:', len(p.functions))"`
  - **Commit**: `feat(transpiler): add numpy shim AST rewriter`
  - _Requirements: FR-6, FR-7_
  - _Design: Component A_

- [ ] 1.4 Add auto-parallelization detection and wrapping
  - **Do**: Add `_is_single_instance(tree: ast.Module) -> bool` function that checks: (a) imports random/numpy, (b) no for-loops with range literal > 100, (c) has top-level assignment to `result` or last statement is expression. Add `_ensure_result_capture(source: str) -> str` that appends `result` variable load before HALT if pattern detected. Modify `execute_python()` in `inference.py` to call auto-parallelizer when `n > 1`. The key insight: EmojiASM GPU instances already return top-of-stack at HALT — just ensure the Python source ends with the result value assigned to a variable and loaded before HALT.
  - **Files**: `emojiasm/transpiler.py`, `emojiasm/inference.py`
  - **Done when**: `execute_python("import random\nx = random.random()\ny = random.random()\nresult = x*x + y*y <= 1.0", n=100)` returns results array with 100 values
  - **Verify**: `python3 -c "from emojiasm.inference import EmojiASMTool; t = EmojiASMTool(prefer_gpu=False); r = t.execute_python('import random\nx = random.random()\ny = random.random()\nresult = x*x + y*y <= 1.0', n=100); print(f'Completed: {r[\"completed\"]}, mean: {r[\"stats\"][\"mean\"]:.2f}')"`
  - **Commit**: `feat(transpiler): add auto-parallelization for single-instance Python`
  - _Requirements: FR-1, FR-2_
  - _Design: Component B_

- [ ] 1.5 Add better error messages with suggestions
  - **Do**: In `transpiler.py`, update error messages: (a) In `visit_Assign`, detect `ast.List` on RHS and suggest `[0.0] * N`. (b) In `visit_For`, when iter is not `range()`, include "Only `for x in range(N)` is supported". (c) In `visit_Import`/`visit_ImportFrom`, when module not in allowed set, include suggestion "Use `import random` + `import math` instead". (d) In `visit_Call`, for unsupported functions, suggest closest supported function. (e) Add `_SUGGESTION_MAP` dict mapping unsupported patterns to suggestions.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: `transpile("x = [1,2,3]")` raises TranspileError containing "Use `arr = [0.0] * N`"
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile, TranspileError; exec(\"try:\\n    transpile('x = [1,2,3]')\\nexcept TranspileError as e:\\n    assert '[0.0] * N' in str(e), str(e)\\n    print('OK:', e)\")"`
  - **Commit**: `feat(transpiler): add actionable error suggestions`
  - _Requirements: FR-8_
  - _Design: Component D_

- [ ] 1.6 Add source map population in transpiler
  - **Do**: In `PythonTranspiler.__init__()`, add `self._source_lines: list[str] = []`. In `transpile()`, after `ast.parse()`, set `compiler._source_lines = source.splitlines()`. In `_emit()`, when `lineno > 0` and `self._source_lines`, set `Instruction.source = self._source_lines[lineno - 1].strip()`. In `__main__.py`, when `--from-python --debug`, iterate over program functions and print `f"  py:{instr.line_num}: {instr.source}  ->  {op_name} {instr.arg}"` to stderr.
  - **Files**: `emojiasm/transpiler.py`, `emojiasm/__main__.py`
  - **Done when**: `emojiasm --from-python examples/montecarlo.py --debug 2>&1 | head` shows Python line -> instruction mapping
  - **Verify**: `python3 -c "from emojiasm.transpiler import transpile; p = transpile('x = 42\nprint(x)'); instr = p.functions['🏠'].instructions[0]; print(f'source={instr.source!r}, line={instr.line_num}'); assert instr.source == 'x = 42'"`
  - **Commit**: `feat(transpiler): populate source maps for Python-to-EmojiASM debugging`
  - _Requirements: FR-9, FR-10_
  - _Design: Component E_

- [ ] 1.7 POC Checkpoint
  - **Do**: Verify all five features work end-to-end: (1) numpy shim transpiles `np.*` code, (2) auto-parallelization wraps single-instance Python, (3) stats include median/histogram, (4) error messages have suggestions, (5) source maps populated
  - **Done when**: All features demonstrable
  - **Verify**: `pytest tests/ -x -q`
  - **Commit**: `feat(tier3): complete POC for LLM agent experience`

## Phase 2: Refactoring

After POC validated, clean up code.

- [ ] 2.1 Extract numpy shim into clean AST transformer class
  - **Do**: Refactor `_rewrite_numpy()` into a proper `NumpyShim(ast.NodeTransformer)` class with clear mapping tables. Add docstrings and type hints. Handle edge cases: `from numpy import *`, `import numpy`, `np = numpy`.
  - **Files**: `emojiasm/transpiler.py`
  - **Done when**: Shim handles all import variants, code is well-documented
  - **Verify**: `pytest tests/ -x -q`
  - **Commit**: `refactor(transpiler): extract NumpyShim as proper AST transformer`
  - _Design: Component A_

- [ ] 2.2 Add error handling for edge cases
  - **Do**: Handle: empty source in auto-parallelize, numpy alias conflicts, source map for multi-line expressions, stats with NaN/inf values, histogram with single unique value. Add guards for all boundary conditions.
  - **Files**: `emojiasm/transpiler.py`, `emojiasm/stats.py`, `emojiasm/inference.py`
  - **Done when**: All edge cases handled gracefully without crashes
  - **Verify**: `pytest tests/ -x -q`
  - **Commit**: `fix(tier3): handle edge cases in numpy shim, stats, and auto-parallel`
  - _Design: Error Handling_

## Phase 3: Testing

- [ ] 3.1 Unit tests for stats module
  - **Do**: Create `tests/test_stats.py`. Test: empty list, single value, normal distribution, median odd/even count, histogram bin counts sum to total, histogram edges monotonic, NaN/inf handling.
  - **Files**: `tests/test_stats.py`
  - **Done when**: 8+ test cases covering all stats functions
  - **Verify**: `pytest tests/test_stats.py -v`
  - **Commit**: `test(stats): add unit tests for unified stats module`
  - _Requirements: AC-2.1, AC-2.2_

- [ ] 3.2 Unit tests for numpy shim
  - **Do**: Add tests to `tests/test_transpiler.py`. Test: `np.random.random()`, `np.sqrt()`, `np.pi`, `np.random.normal()`, `np.random.uniform()`, `np.abs()`, unsupported `np.array()` error, `np.linalg.*` error, alias variants.
  - **Files**: `tests/test_transpiler.py`
  - **Done when**: 8+ test cases covering all numpy mappings and error cases
  - **Verify**: `pytest tests/test_transpiler.py -v -k numpy`
  - **Commit**: `test(transpiler): add numpy shim tests`
  - _Requirements: AC-3.1 through AC-3.7_

- [ ] 3.3 Unit tests for auto-parallelization
  - **Do**: Add tests to `tests/test_transpiler.py`. Test: single-instance detection positive (Monte Carlo pi), negative (has large loop), result capture, execution with n>1, stats in result.
  - **Files**: `tests/test_transpiler.py`
  - **Done when**: 5+ test cases covering detection and wrapping
  - **Verify**: `pytest tests/test_transpiler.py -v -k parallel`
  - **Commit**: `test(transpiler): add auto-parallelization tests`
  - _Requirements: AC-1.1 through AC-1.4_

- [ ] 3.4 Unit tests for error messages and source maps
  - **Do**: Add tests to `tests/test_transpiler.py`. Test: list literal error suggestion, non-range for error, unsupported import error, source map population for simple program, multi-line source maps.
  - **Files**: `tests/test_transpiler.py`
  - **Done when**: 6+ test cases covering error suggestions and source maps
  - **Verify**: `pytest tests/test_transpiler.py -v -k "error or source_map"`
  - **Commit**: `test(transpiler): add error message and source map tests`
  - _Requirements: AC-4.1 through AC-4.5, AC-5.1 through AC-5.3_

## Phase 4: Quality Gates

- [ ] 4.1 Local quality check
  - **Do**: Run all quality checks locally: `pytest tests/ -x -q`, type check if configured, lint check
  - **Verify**: All tests pass, no lint errors
  - **Done when**: All 448+ existing tests pass plus new tests
  - **Commit**: `fix(tier3): address lint/type issues` (if needed)

- [ ] 4.2 Create PR and verify CI
  - **Do**: Push branch, create PR with `gh pr create` referencing issue #29
  - **Verify**: `gh pr checks --watch` all green
  - **Done when**: PR ready for review with all CI checks passing

## Notes

- **POC shortcuts taken**: Numpy shim may not handle all alias patterns initially; auto-parallelizer only detects simple patterns; histogram implementation may be basic
- **Production TODOs**: Full numpy alias support (`from numpy import *`), smarter auto-parallel detection, histogram with custom ranges
