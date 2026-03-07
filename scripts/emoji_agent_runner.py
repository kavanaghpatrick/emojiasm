#!/usr/bin/env python3
"""
emoji_agent_runner.py — parallel EmojiASM runner for LLM agents.

Compiles an .emoji file to a native binary (AOT mode) or falls back to the
Python VM when clang is absent. Runs K instances in parallel via
ProcessPoolExecutor and returns structured JSON.

Usage (CLI):
    python3 emoji_agent_runner.py program.emoji
    python3 emoji_agent_runner.py program.emoji --n 500 --timeout 5
    python3 emoji_agent_runner.py program.emoji --no-compile --output results.json

Importable as a library:
    from emoji_agent_runner import run_parallel
    data = run_parallel("program.emoji", n=200, workers=8)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------

def _extract_number(output: str) -> float | None:
    """Last numeric token on the last non-empty output line."""
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        tokens = line.split()
        for token in reversed(tokens):
            token = token.rstrip(".,;")
            try:
                return float(token)
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# Worker functions (module-level — required for pickling under spawn mode)
# ---------------------------------------------------------------------------

def _run_compiled(binary: str, instance_id: int, timeout: float) -> dict[str, Any]:
    """Run one compiled binary instance. Returns per-instance result dict."""
    import subprocess
    env = {**os.environ, "EMOJI_INSTANCE": str(instance_id)}
    try:
        proc = subprocess.run(
            [binary],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        output = proc.stdout
        numeric = _extract_number(output)
        return {
            "id": instance_id,
            "ok": proc.returncode == 0,
            "numeric": numeric,
            "output": output.strip(),
            "returncode": proc.returncode,
            "error": proc.stderr.strip() if proc.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired:
        return {"id": instance_id, "ok": False, "numeric": None,
                "output": "", "returncode": -1, "error": "timeout"}
    except Exception as exc:
        return {"id": instance_id, "ok": False, "numeric": None,
                "output": "", "returncode": -1, "error": str(exc)}


def _run_interpreted(source: str, instance_id: int, max_steps: int) -> dict[str, Any]:
    """Run one in-process VM instance. Returns per-instance result dict."""
    import io
    from contextlib import redirect_stdout
    from emojiasm.parser import parse, ParseError
    from emojiasm.vm import VM, VMError
    try:
        program = parse(source)
        vm = VM(program)
        vm.max_steps = max_steps
        with redirect_stdout(io.StringIO()):
            buf = vm.run()
        output = "".join(buf)
        numeric = _extract_number(output)
        return {
            "id": instance_id,
            "ok": True,
            "numeric": numeric,
            "output": output.strip(),
            "returncode": 0,
            "error": None,
        }
    except (ParseError, VMError) as exc:
        return {"id": instance_id, "ok": False, "numeric": None,
                "output": "", "returncode": 1, "error": str(exc)}
    except Exception as exc:
        return {"id": instance_id, "ok": False, "numeric": None,
                "output": "", "returncode": 1, "error": str(exc)}


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------

def _try_compile(source: str, opt_level: str) -> str | None:
    """
    Attempt AOT compilation. Returns binary path on success, None otherwise.
    Caller is responsible for unlinking the binary.
    """
    if not shutil.which("clang"):
        return None
    try:
        from emojiasm.parser import parse
        from emojiasm.compiler import compile_program
        program = parse(source)
        return compile_program(program, opt_level=opt_level)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def _stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "count": 0}
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    return {
        "mean": round(mean, 8),
        "std": round(math.sqrt(variance), 8),
        "min": min(values),
        "max": max(values),
        "count": n,
    }


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def run_parallel(
    emoji_file: str | Path,
    n: int = 1000,
    workers: int | None = None,
    timeout: float = 30.0,
    opt_level: str = "-O3",
    force_interpret: bool = False,
    max_steps: int = 1_000_000,
) -> dict[str, Any]:
    """
    Run `n` parallel instances of `emoji_file`.

    Parameters
    ----------
    emoji_file    Path to .emoji source file.
    n             Number of parallel instances to run.
    workers       Worker process count (default: cpu_count()).
    timeout       Per-instance timeout in seconds (compiled mode only).
    opt_level     Clang optimisation flag ('-O0'..'-O3').
    force_interpret  Skip AOT even if clang is available.
    max_steps     VM step limit for interpreted fallback.

    Returns
    -------
    dict with keys: success, error, program, mode, instances, workers,
    total_time_ms, completed, failed, results, stats, message.
    """
    path = Path(emoji_file)
    if not path.exists():
        return _error(f"File not found: {emoji_file}")

    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return _error(f"Cannot read file: {exc}")

    # Validate source (parse check) before spinning up processes
    try:
        from emojiasm.parser import parse, ParseError
        parse(source)
    except Exception as exc:
        return _error(f"Parse error: {exc}")

    actual_workers = workers or os.cpu_count() or 4
    binary: str | None = None
    mode = "interpreted"

    if not force_interpret:
        binary = _try_compile(source, opt_level)
        if binary:
            mode = "compiled"

    start = time.monotonic()
    instance_results: list[dict[str, Any]] = []

    try:
        with ProcessPoolExecutor(max_workers=actual_workers) as executor:
            if mode == "compiled":
                futures = {
                    executor.submit(_run_compiled, binary, i, timeout): i
                    for i in range(n)
                }
            else:
                futures = {
                    executor.submit(_run_interpreted, source, i, max_steps): i
                    for i in range(n)
                }

            per_timeout = timeout if mode == "compiled" else None
            for future in as_completed(futures, timeout=per_timeout):
                try:
                    instance_results.append(future.result(timeout=per_timeout))
                except FuturesTimeout:
                    i = futures[future]
                    instance_results.append({
                        "id": i, "ok": False, "numeric": None,
                        "output": "", "returncode": -1, "error": "timeout",
                    })
                except Exception as exc:
                    i = futures[future]
                    instance_results.append({
                        "id": i, "ok": False, "numeric": None,
                        "output": "", "returncode": -1, "error": str(exc),
                    })
    except Exception as exc:
        return _error(f"Executor failed: {exc}")
    finally:
        if binary and os.path.exists(binary):
            try:
                os.unlink(binary)
            except OSError:
                pass

    elapsed_ms = round((time.monotonic() - start) * 1000, 1)

    ok_results = [r for r in instance_results if r["ok"]]
    failed_count = len(instance_results) - len(ok_results)
    numeric_values = [r["numeric"] for r in ok_results if r["numeric"] is not None]

    return {
        "success": True,
        "error": None,
        "program": str(path),
        "mode": mode,
        "instances": n,
        "workers": actual_workers,
        "total_time_ms": elapsed_ms,
        "completed": len(ok_results),
        "failed": failed_count,
        "results": numeric_values,
        "stats": _stats(numeric_values),
        "message": "Ready for next agent iteration",
    }


def _error(msg: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": msg,
        "program": None,
        "mode": None,
        "instances": 0,
        "workers": 0,
        "total_time_ms": 0.0,
        "completed": 0,
        "failed": 0,
        "results": [],
        "stats": {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "count": 0},
        "message": f"Error: {msg}",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="emoji_agent_runner.py",
        description="Run N parallel EmojiASM instances and return structured JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 emoji_agent_runner.py monte.emoji
  python3 emoji_agent_runner.py monte.emoji --n 500 --workers 8
  python3 emoji_agent_runner.py monte.emoji --no-compile --output results.json
""",
    )
    ap.add_argument("file", help="Path to .emoji source file")
    ap.add_argument("--n", type=int, default=1000, metavar="N",
                    help="Number of parallel instances (default: 1000)")
    ap.add_argument("--workers", type=int, default=None, metavar="N",
                    help="Worker processes (default: cpu_count)")
    ap.add_argument("--timeout", type=float, default=30.0, metavar="SEC",
                    help="Per-instance timeout in seconds (default: 30)")
    ap.add_argument("--opt", default="-O3", metavar="LEVEL",
                    help="Clang optimisation flag (default: -O3)")
    ap.add_argument("--no-compile", action="store_true",
                    help="Force Python VM; skip AOT compilation")
    ap.add_argument("--max-steps", type=int, default=1_000_000,
                    help="VM step limit in interpreted mode (default: 1000000)")
    ap.add_argument("--output", metavar="FILE", default=None,
                    help="Write JSON to FILE instead of stdout")
    ap.add_argument("--pretty", action="store_true", default=True,
                    help="Pretty-print JSON (default: on)")
    ap.add_argument("--compact", action="store_true",
                    help="Compact JSON (overrides --pretty)")
    return ap


def main() -> None:
    ap = _build_parser()
    args = ap.parse_args()

    result = run_parallel(
        emoji_file=args.file,
        n=args.n,
        workers=args.workers,
        timeout=args.timeout,
        opt_level=args.opt,
        force_interpret=args.no_compile,
        max_steps=args.max_steps,
    )

    indent = None if args.compact else 2
    output_json = json.dumps(result, indent=indent)

    if args.output:
        Path(args.output).write_text(output_json + "\n", encoding="utf-8")
        # Still print a brief summary to stdout so agent sees something
        summary = {
            "success": result["success"],
            "mode": result["mode"],
            "completed": result["completed"],
            "failed": result["failed"],
            "total_time_ms": result["total_time_ms"],
            "output_file": args.output,
        }
        print(json.dumps(summary, indent=2))
    else:
        print(output_json)

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
