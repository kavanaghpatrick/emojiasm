"""CLI entry point for EmojiASM."""

import argparse
import json
import os
import subprocess
import sys
from .parser import parse, ParseError
from .vm import VM, VMError
from .disasm import disassemble
from .compiler import compile_to_c, compile_program
from .repl import run_repl
from .agent import run_agent_mode


def main():
    ap = argparse.ArgumentParser(
        prog="emojiasm",
        description="🧬 EmojiASM — Assembly language made of pure emoji",
    )
    ap.add_argument("file", nargs="?", default=None, help="Source file (.emoji)")
    ap.add_argument("-d", "--debug", action="store_true", help="Enable debug tracing 🔍")
    ap.add_argument("--disasm", action="store_true", help="Disassemble only, don't run 📖")
    ap.add_argument("--compile", action="store_true", help="AOT compile to native via C and run")
    ap.add_argument("--emit-c", action="store_true", help="Print generated C source and exit")
    ap.add_argument("--opt", default="-O2", help="Clang optimisation flag for --compile (default: -O2)")
    ap.add_argument("--max-steps", type=int, default=1_000_000, help="Max execution steps")
    ap.add_argument("--repl", action="store_true", help="Launch interactive REPL")
    ap.add_argument("--agent-mode", action="store_true", help="Agent mode: structured JSON output, parallel runs, tracing")
    ap.add_argument("--runs", type=int, default=1, help="Number of parallel instances (agent mode)")
    ap.add_argument("--json", action="store_true", help="Return structured JSON output")
    ap.add_argument("--trace-steps", type=int, default=0, help="Collect trace snapshot every N steps")
    ap.add_argument("--timeout", type=int, default=0, help="Hard-kill each instance after N ms")
    ap.add_argument("--seed", type=int, default=None, help="Base seed for reproducibility")
    args = ap.parse_args()

    if args.repl:
        run_repl()
        return

    if args.file is None:
        ap.error("the following arguments are required: file (or use --repl)")

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"💥 File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    try:
        base_path = os.path.dirname(os.path.abspath(args.file))
        seen_files = {os.path.abspath(args.file)}
        program = parse(source, base_path=base_path, _seen_files=seen_files)
    except ParseError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if args.disasm:
        print(disassemble(program))
        return

    if args.emit_c:
        print(compile_to_c(program))
        return

    if args.agent_mode:
        result = run_agent_mode(
            program,
            filename=args.file,
            runs=args.runs,
            json_output=args.json,
            trace_steps=args.trace_steps,
            timeout_ms=args.timeout,
            seed=args.seed,
            max_steps=args.max_steps,
        )
        print(json.dumps(result, indent=2))
        return

    if args.compile:
        try:
            bin_path = compile_program(program, opt_level=args.opt)
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        try:
            result = subprocess.run([bin_path])
            sys.exit(result.returncode)
        finally:
            os.unlink(bin_path)
        return

    try:
        vm = VM(program, debug=args.debug)
        vm.max_steps = args.max_steps
        vm.run()
    except VMError as e:
        print(f"\n{e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⛔ Interrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
