"""CLI entry point for EmojiASM."""

import argparse
import sys
from .parser import parse, ParseError
from .vm import VM, VMError
from .disasm import disassemble


def main():
    ap = argparse.ArgumentParser(
        prog="emojiasm",
        description="🧬 EmojiASM — Assembly language made of pure emoji",
    )
    ap.add_argument("file", help="Source file (.emoji)")
    ap.add_argument("-d", "--debug", action="store_true", help="Enable debug tracing 🔍")
    ap.add_argument("--disasm", action="store_true", help="Disassemble only, don't run 📖")
    ap.add_argument("--max-steps", type=int, default=1_000_000, help="Max execution steps")
    args = ap.parse_args()

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"💥 File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    try:
        program = parse(source)
    except ParseError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if args.disasm:
        print(disassemble(program))
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
