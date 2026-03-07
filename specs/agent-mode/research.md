---
spec: agent-mode
phase: research
created: 2026-03-07
---

# Research: --agent-mode Feature

## Executive Summary

`--agent-mode` turns EmojiASM into a first-class LLM agent execution engine by adding parallel subprocess spawning, structured JSON output, step-level VM tracing, hard timeout enforcement, and deterministic per-instance seeding. The Python VM already exposes all necessary hooks (output_buffer, steps counter, debug mode). The AOT compiler generates clean C that can accept trace macros via conditional compilation. Effort is L (large) due to multiprocessing reliability edge-cases and the two parallel codepaths (Python VM vs AOT C).

---

## 1. Codebase Findings

### 1.1 Existing File Map

| File | Relevant State |
|------|---------------|
| `emojiasm/__main__.py` | argparse wiring; imports `compile_program`, `VM`; subprocess call for `--compile` |
| `emojiasm/vm.py` | `VM` class; `output_buffer: list[str]`; `steps: int`; `max_steps`; `debug` flag; per-instruction `if self.debug:` branch |
| `emojiasm/compiler.py` | `compile_to_c(program) -> str`; `compile_program(program, opt_level) -> bin_path`; emits C with `goto`-based labels |
| `emojiasm/parser.py` | `parse(source) -> Program`; `Program` / `Function` / `Instruction` dataclasses |
| `emojiasm/opcodes.py` | `Op` IntEnum; `EMOJI_TO_OP` / `OP_TO_EMOJI` dicts |
| `emojiasm/repl.py` | Exists — REPL module |
| `tests/test_cli.py` | `run_cli(source, *args)` helper using `subprocess.run` + tempfile |

### 1.2 VM Architecture — Hooks Available

```
VM.__init__
  .output_buffer: list[str]   # all PRINT/PRINTLN output accumulates here
  .steps: int                 # instruction counter, checked vs max_steps each cycle
  .debug: bool                # if True, prints stack preview to stderr each step
  .halted: bool               # set by HALT opcode
  .stack: list                # full stack accessible after run()
  .memory: dict[str, object]  # named memory cells
  .call_stack: list[tuple]    # call frames
```

The main dispatch loop in `_exec_function` has a single hot path:
```python
self.steps += 1
if self.steps > self.max_steps:
    raise VMError(...)
...
if self.debug:
    print(...)   # current trace hook
```

**Trace hook insertion point**: the `if self.debug:` block at line 85. Adding `if self.trace_every and self.steps % self.trace_every == 0:` immediately after is zero-overhead when `trace_every == 0` (Python short-circuits on falsy int).

### 1.3 Compiler Architecture — C Codegen

`compile_to_c()` produces:
- A preamble with `#define PUSH_N`, `#define POP`, `#define PEEK`
- Static global arrays: `_stk[]`, `_sp`, `_mem*` variables
- Per-function `static void fn_<hex>()` bodies with `goto`-labels
- `int main(void)` that calls the entry function

**Trace macro injection point**: The preamble is built as a string list. A conditional `#ifdef EMOJIASM_TRACE` block can be prepended. Each instruction emission in `_emit_inst` can emit `TRACE(step_counter);` before the instruction's C code.

**Key constraint**: `compile_to_c` currently has no step counter in C. A global `static int _step_count = 0;` would need to be added, incremented before each instruction's C emission, and checked against a `_trace_every` global. This is 2 lines per instruction in C, which on `-O2` will be largely optimized away when `_trace_every == 0`.

### 1.4 CLI Pattern Today

```
emojiasm [file] [--debug] [--disasm] [--compile] [--emit-c] [--opt LEVEL] [--max-steps N] [--repl]
```

All are flat `add_argument` flags on a single parser. The `--compile` flow:
1. Parse source -> `Program`
2. `compile_program(program)` -> `bin_path` (temp file)
3. `subprocess.run([bin_path])` -> exit code
4. `os.unlink(bin_path)`

### 1.5 Process Model

The current `--compile` path uses **subprocess.run** (blocking, single process). No multiprocessing infrastructure exists. The `INPUT`/`INPUT_NUM` opcodes call `input()` / `scanf` — these will block in parallel mode and need suppression or stdin redirection (pipe to `/dev/null`).

### 1.6 Python Constraints

- `requires-python = ">=3.10"` — must support 3.10, 3.11, 3.12, 3.13
- `concurrent.futures.ProcessPoolExecutor.terminate_workers()` and `kill_workers()` added in **3.14** — cannot use these
- `max_tasks_per_child` (ProcessPoolExecutor) added in **3.11** — not available on 3.10
- No external runtime dependencies; stdlib only
- Dev deps: `pytest>=7`, `pytest-cov` only

### 1.7 Pickling Constraints

`ProcessPoolExecutor` requires all task arguments to be picklable. `Program` dataclasses (pure Python with lists/dicts of dataclasses and `Op` IntEnum) are picklable. `VM` instance is not needed cross-process — workers receive source string + config and re-parse independently. This is the correct pattern.

### 1.8 Related Spec

The `developer-experience` spec (in execution phase) adds the REPL and error improvements. It does not touch parallel execution, JSON output, or tracing. No conflict. The `agent-mode` spec may want to leverage the improved error messages from `developer-experience` in its JSON error field.

---

## 2. Web Research Findings

### 2.1 Parallel Execution: ProcessPoolExecutor vs multiprocessing.Pool

| Criterion | `ProcessPoolExecutor` | `multiprocessing.Pool` |
|-----------|----------------------|------------------------|
| API quality | Clean `submit()`/`map()` returning Futures | Older `apply_async`/`map` |
| Timeout on running task | `future.result(timeout=N)` raises `TimeoutError`; **worker keeps running** | Same limitation |
| Cancel pending | `future.cancel()` before start | `AsyncResult` — less clean |
| Kill running worker | Must `.terminate()` on the `Process` object directly; PPE hides these | `pool.terminate()` available |
| Python 3.10 compat | Full | Full |
| Recommendation (2025) | Preferred for new code | Avoid for new code |

**Critical finding**: Neither PPE nor Pool can safely interrupt a running Python task mid-execution. For hard timeout of a Python VM worker, the correct pattern is:

```python
proc = multiprocessing.Process(target=worker_fn, args=(...,))
proc.start()
proc.join(timeout=timeout_sec)
if proc.is_alive():
    proc.terminate()
    proc.join(1)
    if proc.is_alive():
        proc.kill()
        proc.join()
```

For AOT binary workers (`--compile`), timeout is simpler: `subprocess.run([bin], timeout=N)` raises `subprocess.TimeoutExpired` which allows `proc.kill()`.

**Recommended approach for agent-mode**:
- Python VM workers: `multiprocessing.Process` per instance (not Pool) to retain direct `.terminate()`/`.kill()` handles
- AOT binary workers: `subprocess.run([bin_path], timeout=..., capture_output=True)`
- Collect results via `multiprocessing.Queue`

Source: [Killing the ProcessPoolExecutor](https://www.tinybird.co/blog/killing-the-processpoolexecutor), [Python concurrent.futures docs](https://docs.python.org/3/library/concurrent.futures.html)

### 2.2 Deterministic Per-Instance Seeding

**The problem**: forked processes inherit identical RNG state.

**Standard solution** (NumPy docs + community consensus):
```python
# Per-worker seed derivation
worker_seed = hash((base_seed, instance_id)) & 0xFFFFFFFF
random.seed(worker_seed)
```

For EmojiASM (which doesn't use Python's `random` today — no random opcode exists), seeding is passed as an **environment variable** `EMOJIASM_SEED=<value>` so both Python VM and AOT binary workers can read it. The AOT binary would need a `getenv("EMOJIASM_SEED")` call in `main()` to seed `srand()`.

**Derivation formula**: `instance_seed = (base_seed * 6364136223846793005 + instance_id) & 0xFFFFFFFF` (LCG step — produces independent streams without collision).

Source: [NumPy parallel RNG docs](https://numpy.org/doc/stable/reference/random/parallel.html), [multiprocessing and seeded RNGs](https://bbabenko.github.io/multiprocessing-and-seeded-RNGs/)

### 2.3 JSON Output Schema — LLM Tool Response Design

Key findings from OpenAI structured outputs and LLM tooling best practices:
- Schema MUST be versioned (`"schema_version": "1"`) for forward compat
- Errors per-instance must be in the `results` array (not a top-level `errors` list) — avoids positional ambiguity when K > 1
- Output strings should be preserved verbatim (not coerced to numeric) — agent is responsible for interpretation
- Timestamps in ISO 8601 with millisecond precision (`"2026-03-07T12:00:00.123Z"`) for correlation
- `null` is valid for timed-out instances rather than omitting them

Source: [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs), [How JSON Schema Works for LLM Tools](https://blog.promptlayer.com/how-json-schema-works-for-structured-outputs-and-tool-integration/)

### 2.4 VM Tracing — Instrumentation Techniques

From assembly visualizer research (SIGCSE 2025) and dynamic binary instrumentation:
- Step-by-step tracing with stack snapshots is the standard approach (ASM Visualizer does exactly this)
- **Hook insertion point**: before instruction dispatch (pre-execution) is preferred — captures state before side-effects
- **Sampling** (every N steps) is essential for performance — Valgrind-style full tracing is too heavy for agent loops
- **Label tracing** is a separate concern: emit a trace event when execution reaches a label boundary (already known at parse time in EmojiASM)
- Format for LLM consumption: compact JSON lines (`{"step":N,"op":"PUSH","stack":[...],"func":"🏠"}`) are preferred over human-readable multiline

Source: [ASM Visualizer SIGCSE 2025](https://dl.acm.org/doi/10.1145/3641554.3701793)

### 2.5 CLI Design: Flag vs Subcommand

| Approach | Pros | Cons |
|----------|------|------|
| `--agent-mode` flag | Composable with existing flags (`--compile`, `--debug`) | `--agent-mode --parallel 4 --json` is verbose |
| `agent` subcommand | Clean namespace; own help text; mandatory args clear | Breaking change to CLI shape; adds argparse complexity |

**Decision**: Flag is correct here. Rationale:
1. `--compile` already modifies execution mode as a flag — consistent pattern
2. The feature is orthogonal to execution path selection, not a separate workflow
3. `git`-style subcommands are for distinct verbs (commit, push); `agent-mode` modifies how a single verb (run) behaves
4. `--json` should be **independent** of `--agent-mode` (useful standalone)

Source: [Python argparse docs](https://docs.python.org/3/library/argparse.html), [Real Python argparse guide](https://realpython.com/command-line-interfaces-python-argparse/)

### 2.6 Timeout Enforcement

For AOT binary workers (`subprocess.run`):
```python
try:
    result = subprocess.run([bin_path], capture_output=True, timeout=timeout_sec)
except subprocess.TimeoutExpired as e:
    e.process.kill()
    # result is timeout
```

For Python VM workers (`multiprocessing.Process`):
```python
proc = multiprocessing.Process(target=_vm_worker, args=(q, source, cfg))
proc.start()
proc.join(timeout=timeout_sec)
if proc.is_alive():
    proc.terminate()
    proc.join(0.5)
    if proc.is_alive():
        proc.kill()
        proc.join()
    # mark result as timeout
```

`subprocess.TimeoutExpired` is available in Python 3.3+, fully compatible.

### 2.7 Worker Count Default

From Python docs and CPU topology analysis:
- `os.cpu_count()` returns logical CPUs (including hyperthreads)
- For CPU-bound work (VM execution), `cpu_count // 2` or `cpu_count` physical cores is better
- EmojiASM programs run fast; the overhead of spawning 14 processes for a 1ms program dominates
- **Default**: `min(K, os.cpu_count())` where K is user-specified; warn if K > cpu_count * 4
- For `--parallel K` without explicit value: require explicit K (no magic default) — agent always knows how many samples it wants

---

## 3. Design Decisions with Rationale

### 3.1 Flag vs Subcommand

**Decision**: `--agent-mode` is a flag on the existing parser. `--json`, `--parallel`, `--trace-steps`, `--timeout-ms`, `--seed` are all independent flags usable without `--agent-mode`.

**Rationale**: `--json` alone (without parallelism) is useful for scripting. `--trace-steps` is useful for debugging without agent context. Grouping behind `--agent-mode` would hide useful standalone features.

**`--agent-mode` as a semantic flag**: activates validation (e.g., `--parallel` requires `--json`) and sets sensible defaults (`--max-steps` to 100_000, output to stdout only).

### 3.2 Python VM vs AOT for Parallel

**Decision**: Parallel mode uses the Python VM for instances ≤ 64, AOT binary for instances > 64 OR when `--compile` is specified.

**Rationale**:
- Python VM: no compile step, instant startup, easier to instrument; suffers from GIL (mitigated by multiprocessing, not threads)
- AOT binary: faster execution, no GIL, but adds compile latency (clang ~100ms); for K=1000, amortized compile cost is trivial
- The `--compile` flag explicitly opts into AOT; `--parallel` without `--compile` uses Python VM

**Simpler approach for v1**: Always use Python VM for parallel. Add `--compile + --parallel` as v2 enhancement. This eliminates the C trace macro complexity from v1 scope.

### 3.3 Trace Implementation: Python VM Only (v1)

**Decision**: `--trace-steps N` instruments the Python VM only in v1. AOT C trace macros deferred to v2.

**Rationale**:
- AOT trace macros require: (1) step counter global in C, (2) conditional `fprintf` in every instruction, (3) capturing the C output and folding it into JSON — significant complexity
- Python VM trace: add 3 lines to `_exec_function`, serialize to `trace_buffer: list[dict]`
- Zero overhead when `trace_every = 0` (integer falsy check is free)

### 3.4 INPUT Opcode in Parallel Mode

**Decision**: In `--agent-mode`, `INPUT` and `INPUT_NUM` opcodes receive empty string / 0 (stdin redirected to `/dev/null`). Warn at parse time if program uses INPUT with `--agent-mode`.

**Rationale**: LLM agents cannot interactively provide stdin. Silent fallback to empty/0 matches existing EOF behavior in `vm.py:224-228`.

### 3.5 JSON Output Schema

**Decision**: Adopt a flat envelope with per-instance result objects. Separate `traces` from `results`.

See Section 5 for complete schema.

### 3.6 --seed Handling

**Decision**: `--seed S` is an integer. Each instance `i` gets `seed_i = (S * 6364136223846793005 + i) & 0xFFFFFFFF`. Passed to worker as a parameter (not env var in Python VM path). The VM does not currently have a random opcode — seed is future-proofing and for reproducibility logging only. Seed value logged in JSON output.

### 3.7 --agent-mode + --compile Interaction

**Decision**: `--agent-mode --compile` is supported and preferred for large K. Flow:
1. Parse source -> Program
2. `compile_to_c(program)` -> C source
3. `compile_program(program)` -> `bin_path` (once, shared)
4. Spawn K `subprocess.run([bin_path], ...)` with timeout
5. Aggregate stdout from each
6. `os.unlink(bin_path)` in finally

This reuses the existing `compile_program` function without modification.

---

## 4. Design Issues in the Original GitHub Issue

| Issue | Problem | Resolution |
|-------|---------|------------|
| `--binary <compiled_binary>` flag | Adds complexity; compile step is fast; mixing pre-compiled binaries is a security/trust issue | Remove from v1; always compile from source |
| `🤖 📦` new opcode | Adding a new opcode for agent-parallelism mixes VM semantics with execution environment concerns | Do not add; parallelism is a CLI/orchestration concern, not a language primitive |
| `results: [3.14, 3.14, ...]` — array of numbers | Programs may print strings or multiple lines; coercing to number at collection time loses data | `results` is array of `{output: str, exit_code: int, error: str|null, instance_id: int, time_ms: float}` |
| `stats.mean/std/min/max` in JSON | Assumes numeric output; breaks for string programs | Move `stats` to optional field, only present when all outputs are parseable as float |
| `traces` as top-level array | For K > 1, traces are per-instance; top-level array conflates them | Traces go inside each instance's result object |
| `--opt=-O3` default | Original issue says `-O3`; current `--compile` defaults to `-O2`; be consistent | Default `-O2`, user overrides with `--opt` |
| `--trace-labels` auto-instrument | Labels are resolved at parse time to instruction indices; tracing by label means checking `func.labels` inverse map each step | Defer to v2; expensive per-step dict lookup |

---

## 5. Refined Specification

### 5.1 CLI Signature

```
emojiasm <file.emoji> [--agent-mode] [--parallel K] [--json] [--trace-steps N]
                      [--timeout-ms MS] [--seed S] [--compile] [--opt LEVEL]
                      [--max-steps N]
```

All flags are optional and usable independently. `--agent-mode` is a convenience flag that:
- Implies `--json` (unless `--no-json` explicitly given)
- Sets `max_steps` default to 100_000 (tighter guard for agent loops)
- Validates incompatible flags (e.g., `--parallel` without file, INPUT warning)

### 5.2 New argparse Arguments

```python
ap.add_argument("--agent-mode", action="store_true",
                help="Enable agent mode: JSON output + parallel + tracing")
ap.add_argument("--parallel", type=int, default=1, metavar="K",
                help="Run K independent instances in parallel")
ap.add_argument("--json", action="store_true",
                help="Output structured JSON instead of raw stdout")
ap.add_argument("--trace-steps", type=int, default=0, metavar="N",
                help="Emit stack trace every N instructions (0=off)")
ap.add_argument("--timeout-ms", type=int, default=0, metavar="MS",
                help="Hard kill each instance after MS milliseconds (0=no limit)")
ap.add_argument("--seed", type=int, default=None,
                help="Base seed for deterministic per-instance RNG")
```

### 5.3 Complete JSON Output Schema

```json
{
  "schema_version": "1",
  "program": "monte.emoji",
  "instances": 4,
  "wall_time_ms": 42.1,
  "seed": 12345,
  "results": [
    {
      "instance_id": 0,
      "instance_seed": 309158,
      "status": "ok",
      "exit_code": 0,
      "output": "3.14159\n",
      "time_ms": 10.2,
      "steps": 50000,
      "error": null,
      "traces": []
    },
    {
      "instance_id": 1,
      "instance_seed": 309159,
      "status": "timeout",
      "exit_code": null,
      "output": null,
      "time_ms": 5000.0,
      "steps": null,
      "error": "Timeout after 5000ms",
      "traces": []
    },
    {
      "instance_id": 2,
      "instance_seed": 309160,
      "status": "error",
      "exit_code": 1,
      "output": null,
      "time_ms": 0.3,
      "steps": 12,
      "error": "Runtime error at IP=12: Division by zero",
      "traces": []
    }
  ],
  "stats": {
    "ok_count": 1,
    "error_count": 1,
    "timeout_count": 1,
    "numeric_outputs": [3.14159],
    "mean": 3.14159,
    "std": 0.0,
    "min": 3.14159,
    "max": 3.14159
  }
}
```

**Schema field types**:

| Field | Type | Always Present | Notes |
|-------|------|----------------|-------|
| `schema_version` | `"1"` (string) | Yes | Increment on breaking changes |
| `program` | string | Yes | Basename of file |
| `instances` | int | Yes | K |
| `wall_time_ms` | float | Yes | Total elapsed, including spawn overhead |
| `seed` | int or null | Yes | null if not specified |
| `results` | array | Yes | Length == K |
| `results[].instance_id` | int | Yes | 0-indexed |
| `results[].instance_seed` | int or null | Yes | null if seed not specified |
| `results[].status` | `"ok"` \| `"error"` \| `"timeout"` | Yes | |
| `results[].exit_code` | int or null | Yes | null for timeout |
| `results[].output` | string or null | Yes | Raw stdout; null if timeout/crash before output |
| `results[].time_ms` | float | Yes | Per-instance wall time |
| `results[].steps` | int or null | Yes | VM step count; null for AOT/timeout |
| `results[].error` | string or null | Yes | Error message; null if status=ok |
| `results[].traces` | array | Yes | Empty `[]` when trace-steps=0 |
| `traces[].step` | int | — | Instruction count at snapshot |
| `traces[].func` | string | — | Current function name (emoji) |
| `traces[].ip` | int | — | Instruction pointer within function |
| `traces[].op` | string | — | Opcode name (e.g. "PUSH") |
| `traces[].stack` | array | — | Top-5 stack values |
| `stats` | object | Yes | Always present |
| `stats.ok_count` | int | Yes | |
| `stats.error_count` | int | Yes | |
| `stats.timeout_count` | int | Yes | |
| `stats.numeric_outputs` | array of float | Yes | Outputs parseable as float; empty if none |
| `stats.mean` | float or null | Yes | null if numeric_outputs empty |
| `stats.std` | float or null | Yes | null if numeric_outputs empty |
| `stats.min` | float or null | Yes | null if numeric_outputs empty |
| `stats.max` | float or null | Yes | null if numeric_outputs empty |

### 5.4 Trace Event Format

Each entry in `results[i].traces`:

```json
{"step": 1000, "func": "🏠", "ip": 42, "op": "ADD", "stack": [3, 1, 4, 1, 5]}
```

Stack is top-5 values (most recent last, matching Python list ordering). `op` is the `Op` enum name string, not the emoji (more readable and ASCII-safe for LLMs).

### 5.5 VM Trace Hook — Exact Code Pattern

In `emojiasm/vm.py`, `_exec_function`, after `self.steps += 1`:

```python
# TRACE HOOK — zero overhead when trace_every == 0
if self.trace_every and self.steps % self.trace_every == 0:
    self.trace_buffer.append({
        "step": self.steps,
        "func": func_name,
        "ip": ip,
        "op": op.name,
        "stack": self.stack[-5:],
    })
```

New `VM.__init__` additions:
```python
self.trace_every: int = 0        # 0 = disabled
self.trace_buffer: list[dict] = []
```

### 5.6 Worker Architecture

#### Python VM Worker (parallel K, no --compile)

```python
def _vm_worker(queue: multiprocessing.Queue, source: str, cfg: dict) -> None:
    """Runs in a child process. Puts result dict onto queue."""
    import time
    from emojiasm.parser import parse, ParseError
    from emojiasm.vm import VM, VMError
    t0 = time.monotonic()
    try:
        program = parse(source)
        vm = VM(program)
        vm.max_steps = cfg["max_steps"]
        vm.trace_every = cfg["trace_every"]
        vm.run()
        elapsed = (time.monotonic() - t0) * 1000
        queue.put({
            "status": "ok",
            "exit_code": 0,
            "output": "".join(vm.output_buffer),
            "time_ms": round(elapsed, 2),
            "steps": vm.steps,
            "error": None,
            "traces": vm.trace_buffer,
        })
    except (ParseError, VMError) as e:
        elapsed = (time.monotonic() - t0) * 1000
        queue.put({
            "status": "error",
            "exit_code": 1,
            "output": None,
            "time_ms": round(elapsed, 2),
            "steps": getattr(vm, 'steps', None) if 'vm' in dir() else None,
            "error": str(e),
            "traces": [],
        })
```

#### Parallel Orchestrator

```python
def run_parallel(source: str, cfg: AgentConfig) -> list[dict]:
    import multiprocessing, time
    results = []
    procs = []
    queues = []
    timeout_sec = cfg.timeout_ms / 1000 if cfg.timeout_ms else None

    for i in range(cfg.parallel):
        q = multiprocessing.Queue()
        p = multiprocessing.Process(
            target=_vm_worker, args=(q, source, cfg.to_dict()),
            name=f"emojiasm-worker-{i}"
        )
        queues.append(q)
        procs.append(p)

    # Start all
    t_start = time.monotonic()
    for p in procs:
        p.start()

    # Collect with per-process timeout
    for i, (p, q) in enumerate(zip(procs, queues)):
        remaining = None
        if timeout_sec:
            elapsed = time.monotonic() - t_start
            remaining = max(0, timeout_sec - elapsed)
        p.join(timeout=remaining)
        if p.is_alive():
            p.terminate()
            p.join(0.5)
            if p.is_alive():
                p.kill()
                p.join()
            result = {
                "status": "timeout",
                "exit_code": None,
                "output": None,
                "time_ms": cfg.timeout_ms,
                "steps": None,
                "error": f"Timeout after {cfg.timeout_ms}ms",
                "traces": [],
            }
        else:
            try:
                result = q.get_nowait()
            except Exception:
                result = {
                    "status": "error", "exit_code": 1, "output": None,
                    "time_ms": 0, "steps": None, "error": "Worker died without result",
                    "traces": [],
                }
        instance_seed = None
        if cfg.seed is not None:
            instance_seed = (cfg.seed * 6364136223846793005 + i) & 0xFFFFFFFF
        result["instance_id"] = i
        result["instance_seed"] = instance_seed
        results.append(result)

    return results
```

#### AOT Binary Worker (--compile + --parallel)

```python
def _aot_worker(bin_path: str, cfg: AgentConfig, instance_id: int) -> dict:
    import subprocess, time
    timeout_sec = cfg.timeout_ms / 1000 if cfg.timeout_ms else None
    t0 = time.monotonic()
    try:
        r = subprocess.run(
            [bin_path],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            stdin=subprocess.DEVNULL,
        )
        elapsed = (time.monotonic() - t0) * 1000
        return {
            "status": "ok" if r.returncode == 0 else "error",
            "exit_code": r.returncode,
            "output": r.stdout,
            "time_ms": round(elapsed, 2),
            "steps": None,  # AOT has no step counter in v1
            "error": r.stderr.strip() or None if r.returncode != 0 else None,
            "traces": [],
        }
    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - t0) * 1000
        return {
            "status": "timeout", "exit_code": None, "output": None,
            "time_ms": round(elapsed, 2), "steps": None,
            "error": f"Timeout after {cfg.timeout_ms}ms", "traces": [],
        }
```

For AOT parallel, use `concurrent.futures.ProcessPoolExecutor` since subprocess handles its own process lifecycle — no need for manual `.kill()`:

```python
from concurrent.futures import ProcessPoolExecutor, as_completed
with ProcessPoolExecutor(max_workers=min(cfg.parallel, os.cpu_count())) as ex:
    futures = {ex.submit(_aot_worker, bin_path, cfg, i): i for i in range(cfg.parallel)}
    for fut in as_completed(futures):
        i = futures[fut]
        results[i] = fut.result()
```

### 5.7 Stats Computation

```python
def _compute_stats(results: list[dict]) -> dict:
    ok = sum(1 for r in results if r["status"] == "ok")
    err = sum(1 for r in results if r["status"] == "error")
    tout = sum(1 for r in results if r["status"] == "timeout")
    numeric = []
    for r in results:
        if r["output"] is not None:
            try:
                numeric.append(float(r["output"].strip()))
            except ValueError:
                pass
    mean = sum(numeric) / len(numeric) if numeric else None
    variance = sum((x - mean) ** 2 for x in numeric) / len(numeric) if len(numeric) > 1 else 0.0
    std = variance ** 0.5 if numeric else None
    return {
        "ok_count": ok,
        "error_count": err,
        "timeout_count": tout,
        "numeric_outputs": numeric,
        "mean": round(mean, 6) if mean is not None else None,
        "std": round(std, 6) if std is not None else None,
        "min": round(min(numeric), 6) if numeric else None,
        "max": round(max(numeric), 6) if numeric else None,
    }
```

Note: `math.sqrt` and `statistics` are stdlib; using `** 0.5` avoids the import.

### 5.8 New Module: `emojiasm/agent.py`

All agent-mode logic lives in a new module to avoid bloating `__main__.py`.

```
emojiasm/
  agent.py          # AgentConfig, _vm_worker, run_parallel, _aot_worker, _compute_stats
  __main__.py       # wires --agent-mode, --parallel, --json, --trace-steps, --timeout-ms, --seed
```

`__main__.py` imports lazily:
```python
if args.agent_mode or args.json or args.parallel > 1:
    from .agent import run_agent_mode
    run_agent_mode(source, program, args)
    return
```

### 5.9 `__main__.py` Agent Mode Handler (outline)

```python
def _run_agent_mode(source: str, program, args) -> None:
    import json, os, time
    from .agent import AgentConfig, run_parallel, run_parallel_aot, _compute_stats
    from .compiler import compile_program

    cfg = AgentConfig(
        parallel=args.parallel,
        trace_every=args.trace_steps,
        timeout_ms=args.timeout_ms,
        seed=args.seed,
        max_steps=args.max_steps,
    )

    t0 = time.monotonic()
    if args.compile:
        bin_path = compile_program(program, opt_level=args.opt)
        try:
            results = run_parallel_aot(bin_path, cfg)
        finally:
            os.unlink(bin_path)
    else:
        results = run_parallel(source, cfg)
    wall_ms = round((time.monotonic() - t0) * 1000, 2)

    if args.json or args.agent_mode:
        import os.path
        output = {
            "schema_version": "1",
            "program": os.path.basename(args.file),
            "instances": cfg.parallel,
            "wall_time_ms": wall_ms,
            "seed": cfg.seed,
            "results": results,
            "stats": _compute_stats(results),
        }
        print(json.dumps(output, ensure_ascii=False))
    else:
        # --parallel without --json: print each output separated by ---
        for r in results:
            if r["output"]:
                print(r["output"], end="")
```

---

## 6. Acceptance Criteria (Testable)

| # | Criterion | Test Method |
|---|-----------|-------------|
| AC-1 | `--json` flag produces valid JSON on stdout | `json.loads(result.stdout)` succeeds |
| AC-2 | JSON schema_version is `"1"` | `output["schema_version"] == "1"` |
| AC-3 | `results` length equals `--parallel K` | `len(output["results"]) == K` |
| AC-4 | Each result has `status`, `output`, `time_ms`, `error`, `traces` | Assert all keys present |
| AC-5 | `--parallel 1` single instance JSON matches direct run output | Compare `output` field |
| AC-6 | `--parallel 4` spawns 4 independent workers, all complete | `ok_count == 4` in stats |
| AC-7 | `--trace-steps 1` produces traces for every step | `len(traces) == steps` |
| AC-8 | `--trace-steps 0` produces empty traces | `traces == []` |
| AC-9 | `--timeout-ms 1` kills an infinite-loop program | `status == "timeout"` |
| AC-10 | `--timeout-ms` does not affect a fast program | Fast program still `status == "ok"` |
| AC-11 | `--seed 42 --parallel 4` produces instance_seeds 0..3, deterministic | Re-run with same seed, same seeds |
| AC-12 | `--agent-mode` implies `--json` output (no separate `--json` needed) | `json.loads(result.stdout)` succeeds |
| AC-13 | `--compile --parallel 4` AOT path works end-to-end | `ok_count == 4`, clang-skipif |
| AC-14 | `--json` without `--parallel` (K=1) still produces valid JSON | Single result in `results` |
| AC-15 | Existing tests unaffected (no stdout when flags not set) | `pytest tests/` passes |
| AC-16 | `stats.mean` is null for string-output programs | Assert `None` |
| AC-17 | `stats.mean` is correct float for numeric-output programs | Assert within 1e-6 |
| AC-18 | Worker crash (simulated) produces `status=error` not Python traceback | Check result, no traceback in stdout |

---

## 7. Implementation Complexity Estimate

| Component | Complexity | Notes |
|-----------|------------|-------|
| `emojiasm/agent.py` — new module | M | ~150-200 LOC; most complex part is process management |
| `VM` trace hook additions | S | 5 LOC change; `trace_every`, `trace_buffer` attrs |
| `__main__.py` wiring | S | 6 new `add_argument` calls + `_run_agent_mode` delegation |
| JSON output + stats | S | Pure Python; ~50 LOC |
| Test suite additions | M | ~100-120 LOC; process-based tests need careful teardown |
| AOT parallel path | S | Thin wrapper over existing `compile_program` + `ProcessPoolExecutor` |
| **Total estimate** | **L** | ~400 LOC net-new; 2-3 days focused work |

**Complexity drivers**:
1. Cross-process communication (Queue) reliability and exception paths
2. Timeout enforcement correctness across 3.10–3.13
3. Ensuring no stdout pollution in existing non-agent paths
4. Test isolation (child processes must not inherit pytest fixtures)

---

## 8. Implementation Risk Areas

| Risk | Severity | Mitigation |
|------|----------|------------|
| Orphaned child processes on test failure | High | Wrap all process management in try/finally; use `multiprocessing.active_children()` cleanup |
| `multiprocessing` start method on macOS (spawn vs fork) | Medium | macOS defaults to `spawn` since Python 3.8; `spawn` is slower but safe; explicitly set `mp_context = multiprocessing.get_context("spawn")` for consistency across platforms |
| Queue deadlock when child fills OS pipe buffer | Medium | `Queue` uses a background thread; safe for normal output sizes; add `maxsize=0` (unlimited) |
| `json.dumps` with emoji keys/values | Low | Python's `json` module handles Unicode correctly; `ensure_ascii=False` preserves emoji |
| `steps` field null for AOT path | Low | Document clearly; agents should not rely on `steps` when `--compile` is used |
| Parallel K >> cpu_count slows machine | Low | Cap effective parallelism at `min(K, cpu_count * 2)` by default; log warning |
| `--trace-steps` with AOT `--compile` | Medium | Not supported in v1; raise `argparse` error if both specified with trace-steps > 0 |
| CI: multiprocessing in pytest on 3.10 | Medium | Use `if __name__ == "__main__"` guard — not needed in library code; subprocess-based tests are safe in CI |

---

## 9. Quality Commands

| Type | Command | Source |
|------|---------|--------|
| Test (all) | `python -m pytest tests/ -v --cov=emojiasm` | CI workflow (`ci.yml`) |
| Test (single) | `pytest tests/test_cli.py::test_hello_world` | CLAUDE.md |
| TypeCheck | Not configured | Not found |
| Lint | Not configured | Not found |
| Build | `pip install -e .` | CLAUDE.md |

**Local CI**: `python -m pytest tests/ -v --cov=emojiasm --cov-report=term-missing`

---

## 10. Related Specs

| Spec | Relationship | May Need Update |
|------|-------------|-----------------|
| `developer-experience` | In execution phase; adds REPL + error improvements. Error message format changes (VMError, ParseError) will flow into agent-mode's `error` JSON field. | No — agent-mode depends on it, not vice versa |

---

## Sources

- [Python concurrent.futures docs](https://docs.python.org/3/library/concurrent.futures.html)
- [Killing the ProcessPoolExecutor — Tinybird](https://www.tinybird.co/blog/killing-the-processpoolexecutor)
- [NumPy parallel random number generation](https://numpy.org/doc/stable/reference/random/parallel.html)
- [Multiprocessing and seeded RNGs — bbabenko](https://bbabenko.github.io/multiprocessing-and-seeded-RNGs/)
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [How JSON Schema Works for LLM Tools — PromptLayer](https://blog.promptlayer.com/how-json-schema-works-for-structured-outputs-and-tool-integration/)
- [ASM Visualizer SIGCSE 2025](https://dl.acm.org/doi/10.1145/3641554.3701793)
- [Python argparse docs](https://docs.python.org/3/library/argparse.html)
- [Real Python argparse guide](https://realpython.com/command-line-interfaces-python-argparse/)
- [Cancel running work in ProcessPoolExecutor — Python Discuss](https://discuss.python.org/t/cancel-running-work-in-processpoolexecutor/58605)
- GitHub issue #10: `kavanaghpatrick/emojiasm`
- `/Users/patrickkavanagh/emojiasm/emojiasm/__main__.py`
- `/Users/patrickkavanagh/emojiasm/emojiasm/vm.py`
- `/Users/patrickkavanagh/emojiasm/emojiasm/compiler.py`
- `/Users/patrickkavanagh/emojiasm/emojiasm/parser.py`
- `/Users/patrickkavanagh/emojiasm/emojiasm/opcodes.py`
- `/Users/patrickkavanagh/emojiasm/tests/test_cli.py`
