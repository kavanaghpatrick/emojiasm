#!/usr/bin/env python3
"""
Benchmark EmojiASM against other language runtimes.
Task: sum integers 1..50000 (result = 1,250,025,000)
"""

import subprocess
import time
import sys
import os
import statistics
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

RUNS = 5
N = 50_000
EXPECTED = N * (N + 1) // 2  # 1_250_025_000
# EmojiASM needs ~650k instructions; use 2M to be safe
EMOJIASM_MAX_STEPS = 2_000_000


def time_cmd(cmd: list[str], runs: int = RUNS) -> tuple[float, str]:
    """Return (median_seconds, stdout_stripped)."""
    times = []
    out = ""
    for _ in range(runs):
        t0 = time.perf_counter()
        r = subprocess.run(cmd, capture_output=True, text=True)
        t1 = time.perf_counter()
        if r.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{r.stderr}")
        times.append(t1 - t0)
        out = r.stdout.strip()
    return statistics.median(times), out


def time_compiled_emojiasm(opt: str, runs: int = RUNS) -> tuple[float, str]:
    """AOT compile sum_n.emoji then benchmark the native binary."""
    sys.path.insert(0, ROOT)
    from emojiasm.parser import parse
    from emojiasm.compiler import compile_program

    with open(os.path.join(HERE, "sum_n.emoji"), "r", encoding="utf-8") as f:
        source = f.read()

    program = parse(source)
    bin_path = compile_program(program, opt_level=opt)

    try:
        times = []
        out = ""
        for _ in range(runs):
            t0 = time.perf_counter()
            r = subprocess.run([bin_path], capture_output=True, text=True)
            t1 = time.perf_counter()
            times.append(t1 - t0)
            out = r.stdout.strip()
        return statistics.median(times), out
    finally:
        os.unlink(bin_path)


def time_emojiasm_internal(runs: int = RUNS) -> tuple[float, int]:
    """Time EmojiASM with Python import overhead excluded (parse+run only)."""
    sys.path.insert(0, ROOT)
    from emojiasm.parser import parse
    from emojiasm.vm import VM

    with open(os.path.join(HERE, "sum_n.emoji"), "r", encoding="utf-8") as f:
        source = f.read()

    times = []
    for _ in range(runs):
        program = parse(source)
        vm = VM(program)
        vm.max_steps = EMOJIASM_MAX_STEPS
        t0 = time.perf_counter()
        vm.run()
        t1 = time.perf_counter()
        times.append(t1 - t0)

    return statistics.median(times), int(vm.output_buffer[0])


def check(label: str, output: str):
    val = int(output.strip())
    if val != EXPECTED:
        print(f"  WRONG ANSWER for {label}: got {val}, expected {EXPECTED}")


print(f"Benchmark: sum(1..{N:,}) = {EXPECTED:,}")
print(f"Runs per candidate: {RUNS} (reporting median)\n")

results = []

# 1. EmojiASM — full subprocess (includes Python startup)
print("Timing EmojiASM (subprocess, includes Python startup)...")
t, out = time_cmd(
    [sys.executable, "-m", "emojiasm", "--max-steps", str(EMOJIASM_MAX_STEPS),
     os.path.join(HERE, "sum_n.emoji")],
    runs=RUNS,
)
check("EmojiASM subprocess", out)
results.append(("EmojiASM (subprocess)", t))

# 2. EmojiASM — parse+run only (no Python startup overhead)
print("Timing EmojiASM (in-process, VM execution only)...")
t_vm, val = time_emojiasm_internal()
if val != EXPECTED:
    print(f"  WRONG ANSWER: got {val}")
results.append(("EmojiASM (VM only)", t_vm))

# 3. Python (same interpreter — shows pure interpreter overhead)
print("Timing Python...")
t, out = time_cmd([sys.executable, os.path.join(HERE, "sum_n.py")])
check("Python", out)
results.append(("Python 3 (while loop)", t))

# 4. Node.js
print("Timing Node.js...")
try:
    t, out = time_cmd(["node", os.path.join(HERE, "sum_n.js")])
    check("Node.js", out)
    results.append(("Node.js (v8 JIT)", t))
except (FileNotFoundError, RuntimeError) as e:
    print(f"  skipped: {e}")

# 5. Lua
print("Timing Lua...")
try:
    t, out = time_cmd(["lua", os.path.join(HERE, "sum_n.lua")])
    check("Lua", out)
    results.append(("Lua 5.4", t))
except (FileNotFoundError, RuntimeError) as e:
    print(f"  skipped: {e}")

# 6. Ruby
print("Timing Ruby...")
try:
    t, out = time_cmd(["ruby", os.path.join(HERE, "sum_n.rb")])
    check("Ruby", out)
    results.append(("Ruby", t))
except (FileNotFoundError, RuntimeError) as e:
    print(f"  skipped: {e}")

# 7a. C (compiled, -O2) — constant-folded (N hardcoded)
print("Timing C constant-folded (clang -O2, N hardcoded)...")
try:
    t, out = time_cmd([os.path.join(HERE, "sum_n")])
    check("C constant-folded", out)
    results.append(("C -O2 (constant-folded!)", t))
except (FileNotFoundError, RuntimeError) as e:
    print(f"  skipped: {e}")

# 7b. C (compiled, -O2) — runtime N, fair comparison
print("Timing C runtime-N (clang -O2)...")
try:
    t, out = time_cmd([os.path.join(HERE, "sum_n_runtime"), str(N)])
    check("C runtime", out)
    results.append(("C -O2 (runtime N)", t))
except (FileNotFoundError, RuntimeError) as e:
    print(f"  skipped: {e}")

# 7c. C (compiled, -O3) — runtime N
print("Timing C runtime-N (clang -O3)...")
try:
    t, out = time_cmd([os.path.join(HERE, "sum_n_runtime_O3"), str(N)])
    check("C runtime O3", out)
    results.append(("C -O3 (runtime N)", t))
except (FileNotFoundError, RuntimeError) as e:
    print(f"  skipped: {e}")

# 8. EmojiASM compiled to C, clang -O2
print("Timing EmojiASM compiled (clang -O2)...")
try:
    t, out = time_compiled_emojiasm("-O2")
    check("EmojiASM compiled -O2", out)
    results.append(("EmojiASM → C (clang -O2)", t))
except Exception as e:
    print(f"  skipped: {e}")

# 9. EmojiASM compiled to C, clang -O3
print("Timing EmojiASM compiled (clang -O3)...")
try:
    t, out = time_compiled_emojiasm("-O3")
    check("EmojiASM compiled -O3", out)
    results.append(("EmojiASM → C (clang -O3)", t))
except Exception as e:
    print(f"  skipped: {e}")

# ── Results ────────────────────────────────────────────────────────────────
EMOJIASM_INSTRUCTIONS = 13 * N  # approximate: 13 ops/iteration

print()
print("=" * 65)
print(f"{'Candidate':<28} {'Time (ms)':>10} {'vs EmojiASM VM':>15}")
print("=" * 65)

vm_time = next(t for name, t in results if name == "EmojiASM (VM only)")

for name, t in results:
    if name == "EmojiASM (VM only)":
        bar = "baseline"
    elif t < vm_time:
        bar = f"{vm_time / t:.0f}x faster"
    else:
        bar = f"{t / vm_time:.0f}x slower"
    print(f"  {name:<26} {t*1000:>9.1f}ms   {bar:>14}")

print("=" * 65)
print(f"\nEmojiASM VM throughput: ~{EMOJIASM_INSTRUCTIONS / vm_time / 1e6:.2f}M instructions/sec")
print(f"Python overhead factor: {vm_time / next(t for n,t in results if 'Python' in n):.1f}x "
      f"(EmojiASM VM time / raw Python time)")
