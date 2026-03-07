---
spec: developer-experience / emoji_agent_runner.py
phase: research
created: 2026-03-07
issue: https://github.com/kavanaghpatrick/emojiasm/issues/11
---

# Research: emoji_agent_runner.py

## Executive Summary

The AOT compiler exists and works (`emojiasm/compiler.py` -> C -> clang). The issue's prototype has six fixable flaws: it assumes a `-o` flag that `__main__.py` does not support, it parses `"≈"` (too fragile), it drops all per-instance errors silently, it leaks the compiled binary on exception, it uses `statistics` math inline (fine), and it ignores `EMOJI_SEED` (the VM has no RNG, so the env var does nothing today). The best design uses `concurrent.futures.ProcessPoolExecutor` for cleaner timeout/error propagation, falls back to the in-process Python VM when `clang` is absent, and supports arbitrary output programs by parsing the last numeric token rather than a hard-coded delimiter.

---

## Codebase Analysis

### AOT compiler chain (`emojiasm/compiler.py`)

- `compile_to_c(program: Program) -> str` — emits a full C program.
- `compile_program(program: Program, opt_level='-O2') -> str` — writes temp `.c`, runs `clang`, returns **path to binary** (caller must `unlink`).
- `__main__.py` `--compile` flag calls these and then `subprocess.run([bin_path])`, then `os.unlink(bin_path)`. There is **no `-o` flag** in the existing CLI. The issue prototype passes `--opt=-O3` and `-o` to `emojiasm` — that `-o` flag does not exist. Fix: call `compile_program()` directly via the Python API, or use a temp directory.

### VM (`emojiasm/vm.py`)

- `VM(program, debug=False)` — stack machine, no built-in RNG.
- `vm.run()` returns `self.output_buffer: list[str]`.
- Each `VM()` instance is fully isolated; safe to create N of them in-process.
- `max_steps` defaults to 1,000,000 — controllable per-instance.
- `VMError` raised on runtime errors; `ParseError` on bad source.
- `output_buffer` captures everything printed — no need to intercept stdout for in-process runs.

### Test pattern (`tests/test_emojiasm.py:7-11`)

```python
def run(source: str, max_steps: int = 10000) -> list[str]:
    program = parse(source)
    vm = VM(program)
    vm.max_steps = max_steps
    return vm.run()
```

This is the canonical in-process invocation. `emoji_agent_runner.py` can use the same pattern for the fallback mode, wrapped in a `try/except (ParseError, VMError)`.

### Package structure

- `pyproject.toml`: `requires-python = ">=3.10"`, no runtime deps beyond stdlib.
- Entry point: `emojiasm = "emojiasm.__main__:main"`.
- `multiprocessing` default start method on macOS: **spawn** (confirmed: `mp.get_start_method() == 'spawn'`).

### Environment

- `clang` present at `/usr/bin/clang` (Apple clang 17.0.0).
- `cpu_count()` = 14 on this machine.
- Python 3.11; `concurrent.futures` is stdlib.

---

## Critical Design Issues in the Issue Prototype

| Issue | Prototype code | Fix |
|---|---|---|
| `-o` flag doesn't exist | `["emojiasm", "--compile", "--opt=-O3", str(file), "-o", str(binary)]` | Call `compile_program()` directly |
| Binary path collides across N runs | Single `binary` path, all N processes run same binary | OK — binary is read-only; safe to run in parallel |
| `"≈"` parse is fragile | Only works for π estimators | Parse last numeric token on last non-empty line |
| `EMOJI_SEED` env var has no effect | VM has no RNG; env is not passed to VM | Document as no-op today; useful for future RNG opcode |
| Binary not cleaned up on exception | No `try/finally` around Pool | Use `try/finally` or `atexit` |
| `results[:10] + ["…"]` breaks JSON type | Mix of float and str in same array | Use `results_sample` as separate key |
| Silent failures | `except Exception: return 0.0` | Track per-instance errors, expose `errors` count |

---

## External Research

### Pool vs ProcessPoolExecutor

**Source**: [superfastpython.com](https://superfastpython.com/multiprocessing-pool-vs-processpoolexecutor/)

| Concern | Pool | ProcessPoolExecutor |
|---|---|---|
| Timeout per task | Manual via `async_result.get(timeout=N)` | `future.result(timeout=N)` — clean |
| Exception propagation | Suppresses unless you check `AsyncResult` | Re-raises in caller via `Future` |
| Cancel remaining on first error | No built-in | `executor.shutdown(cancel_futures=True)` |
| `chunksize` | Must set manually | Auto-optimized |
| `if __name__ == "__main__"` guard | Required (spawn mode) | Required |

**Decision**: Use `ProcessPoolExecutor` with `as_completed()` for per-task timeout and per-task error tracking.

### Parallel Monte Carlo pattern

**Source**: [Agustinus Kristiadi](https://agustinus.kristia.de/blog/parallel-monte-carlo/), [Duke STA663](https://people.duke.edu/~ccc14/sta-663-2020/notebooks/S10B_Multicore_Parallelism.html)

Standard pattern:
```python
with ProcessPoolExecutor(max_workers=N) as ex:
    futures = [ex.submit(run_one, args) for _ in range(K)]
    results = [f.result(timeout=T) for f in as_completed(futures)]
```

Key: seed randomness **per-worker** (in compiled binary: seed from process PID, not env var, since C `rand()` defaults to seed 1 unless seeded). For the Python VM fallback, seed per-call with `random.seed(instance_id)` in the worker function.

### LLM agent JSON schema design

**Source**: [promptlayer.com](https://blog.promptlayer.com/how-json-schema-works-for-structured-outputs-and-tool-integration/), [agenta.ai](https://agenta.ai/blog/the-guide-to-structured-outputs-and-function-calling-with-llms)

Best practices for agent-consumed JSON:
1. **`success: bool`** at top level — agent can branch immediately.
2. **`error: str | null`** — always present, even when success=true (null).
3. **Flat stats dict** — agents parse better than nested objects.
4. **`mode: "compiled" | "interpreted"`** — tells agent what it's comparing across runs.
5. **`results_sample`** separate from `results` — keep full array; sample for readability.
6. **All numeric types must be JSON-native** — no `"..."` mixed into float arrays.

### Subprocess timeout (cross-platform)

**Source**: [Python docs](https://docs.python.org/3/library/multiprocessing.html), [pythonspeed.com](https://pythonspeed.com/articles/python-multiprocessing/)

- `subprocess.run(..., timeout=N)` raises `subprocess.TimeoutExpired` on timeout.
- `ProcessPoolExecutor` + `future.result(timeout=N)` raises `concurrent.futures.TimeoutError`.
- Both are cross-platform (POSIX + Windows).
- **macOS caveat**: default start method is `spawn`, not `fork`. Worker functions must be importable at module level (not lambdas, not closures over non-picklable objects).

---

## Parallelism Decision

**Mode A — Compiled binary** (when `clang` is available):
- `compile_program()` once, get temp binary path.
- Submit `subprocess.run([binary], timeout=T)` across K workers in `ProcessPoolExecutor`.
- Each subprocess is fully isolated: its own process, heap, RNG state seeded from PID.
- No pickling of VM state required — only path strings cross the process boundary.

**Mode B — Python VM** (fallback when clang missing or compilation fails):
- Worker function: `parse(source)` then `VM(program).run()` — fully isolated per call.
- `program` (a `Program` dataclass) IS picklable (dataclasses with stdlib-typed fields).
- Pass `source: str` across boundary, re-parse in each worker to avoid pickle of complex objects.
- **Important**: on macOS with `spawn`, the `emojiasm` package must be importable in the worker. It is, since it's installed in the conda env.

**Chunksize**: Not needed — `ProcessPoolExecutor` with `submit()` (not `map()`) handles it implicitly. Each task is one `subprocess.run` or one VM execution.

---

## Output Parsing Strategy

The issue's `"≈"` approach is program-specific. Better: **last numeric token on last non-empty line**.

```python
def _extract_number(output: str) -> float | None:
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line:
            # Try last whitespace-separated token
            token = line.split()[-1]
            try:
                return float(token)
            except ValueError:
                pass
    return None
```

This works for:
- `"3.14159"` — direct number
- `"pi ≈ 3.14159"` — last token is number
- `"Computing result: 90"` — last token is number
- `"Hello world"` — returns None (non-numeric output)

For non-numeric output programs, the runner still works — `raw_output` is captured; `numeric_value` is `null` in JSON. The agent can inspect `results_raw` instead.

---

## JSON Schema (Final)

```json
{
  "success": true,
  "error": null,
  "program": "monte.emoji",
  "mode": "compiled",
  "instances": 1000,
  "workers": 14,
  "total_time_ms": 3420.1,
  "completed": 998,
  "failed": 2,
  "results": [3.141200, 3.140800, 3.139900],
  "results_sample_size": 10,
  "stats": {
    "mean": 3.141590,
    "std": 0.012300,
    "min": 3.10,
    "max": 3.18,
    "count": 998
  },
  "message": "Ready for next agent iteration"
}
```

Key design choices:
- `results` = all numeric values (not truncated) — agent needs them for real analysis.
- `results_sample_size` = how many are shown in a summary context.
- `completed` / `failed` = separate counts; `failed` > 0 does not make `success: false`.
- `success: false` only when the entire run cannot execute (parse error, compile failure).
- `mode` tells agent whether it got native speed or interpreted speed.

---

## CLI Design

```
emoji_agent_runner.py <file.emoji> [options]

Options:
  --n N          Number of parallel instances (default: 1000)
  --workers N    Worker processes (default: cpu_count())
  --timeout N    Seconds per instance (default: 10)
  --output FILE  Write JSON to FILE instead of stdout
  --no-compile   Force Python VM even if clang available
  --max-steps N  VM step limit in fallback mode (default: 1_000_000)
```

`argparse` — not `sys.argv` parsing. The issue uses ad-hoc `sys.argv` which breaks for `--n` at non-fixed positions.

---

## Quality Commands

| Type | Command | Source |
|---|---|---|
| Lint | Not configured | pyproject.toml |
| TypeCheck | Not configured | pyproject.toml |
| Unit Test | `pytest` | pyproject.toml `[tool.pytest.ini_options]` |
| Test (single) | `pytest tests/test_emojiasm.py::test_NAME` | CLAUDE.md |
| Build | `pip install -e .` | CLAUDE.md |
| Coverage | `pytest --cov` | pyproject.toml dev dep |

**Local CI**: `pytest && pip install -e . --quiet`

---

## Related Specs

| Spec | Domain | Relationship | mayNeedUpdate |
|---|---|---|---|
| `developer-experience` | DX tooling | This runner is part of this spec | No — additive |
| `agent-mode` (issue #10) | VM `--agent-mode` flag | Runner pairs with it; runner works without it | No |

---

## Feasibility Assessment

| Aspect | Assessment | Notes |
|---|---|---|
| Technical Viability | High | Both modes confirmed working; no new deps |
| Effort Estimate | S | ~150 lines, one file |
| Risk Level | Low | Purely additive; no existing API changes |

---

## Recommendations

1. **Use `compile_program()` directly**, not `emojiasm --compile -o ...` — the `-o` flag doesn't exist. Import `emojiasm.compiler.compile_program` and `emojiasm.parser.parse`.

2. **Dual-mode with `clang` detection**: `shutil.which("clang")` before attempting AOT. Emit `"mode": "interpreted"` in JSON when fallback used.

3. **Use `ProcessPoolExecutor` + `as_completed()`** — better per-task timeout and error propagation than `Pool.starmap`. Critical for K=1000 where some instances may hang.

4. **Parse last numeric token**, not `"≈"`. Makes the runner useful for any numeric-output EmojiASM program.

5. **Expose `results` as full float list**, not truncated. Agents need real data. Add `results_sample_size` for display.

6. **Track `failed` count separately** — don't collapse errors into `0.0` silently.

7. **Guard with `if __name__ == "__main__"`** — required for `spawn` start method on macOS/Windows.

8. **Make importable as library** — `from emoji_agent_runner import run_parallel` should work without side effects. All top-level code inside `if __name__ == "__main__"`.

9. **Clean up binary in `try/finally`** — the issue prototype leaks the temp binary on exception.

10. **File location**: `scripts/emoji_agent_runner.py` (matches issue spec; `scripts/` already has `kb`).

---

## Sources

- [GitHub issue #11](https://github.com/kavanaghpatrick/emojiasm/issues/11)
- [superfastpython.com: Pool vs ProcessPoolExecutor](https://superfastpython.com/multiprocessing-pool-vs-processpoolexecutor/)
- [Python docs: concurrent.futures](https://docs.python.org/3/library/concurrent.futures.html)
- [Python docs: multiprocessing](https://docs.python.org/3/library/multiprocessing.html)
- [Agustinus Kristiadi: Parallel Monte Carlo](https://agustinus.kristia.de/blog/parallel-monte-carlo/)
- [promptlayer.com: JSON Schema for LLM tools](https://blog.promptlayer.com/how-json-schema-works-for-structured-outputs-and-tool-integration/)
- [agenta.ai: Structured outputs guide](https://agenta.ai/blog/the-guide-to-structured-outputs-and-function-calling-with-llms)
- [pythonspeed.com: multiprocessing pitfalls](https://pythonspeed.com/articles/python-multiprocessing/)
- `/Users/patrickkavanagh/emojiasm/emojiasm/compiler.py`
- `/Users/patrickkavanagh/emojiasm/emojiasm/vm.py`
- `/Users/patrickkavanagh/emojiasm/emojiasm/__main__.py`
- `/Users/patrickkavanagh/emojiasm/tests/test_emojiasm.py`
