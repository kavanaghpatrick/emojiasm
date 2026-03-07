"""Interactive REPL for EmojiASM."""

import sys

from .opcodes import EMOJI_TO_OP, Op
from .parser import parse, ParseError
from .vm import VM, VMError


def _make_single_instruction_program(line: str):
    """Wrap a single instruction line in a minimal 🏠 function and parse it."""
    return parse(f"📜 🏠\n  {line}")


def _handle_meta(cmd: str, state: dict) -> bool:
    """Handle REPL meta-commands. Returns False to signal exit, True to continue."""
    cmd = cmd.strip()
    if cmd in (":quit", ":exit"):
        return False
    if cmd == ":reset":
        state["stack"].clear()
        state["memory"].clear()
        print("  (state reset)")
        return True
    if cmd == ":mem":
        mem = state["memory"]
        if mem:
            for k, v in mem.items():
                print(f"  {k} = {v!r}")
        else:
            print("  (memory empty)")
        return True
    if cmd == ":help":
        print("  Opcodes:")
        for emoji, op in EMOJI_TO_OP.items():
            print(f"    {emoji}  {op.name}")
        print("  Meta commands: :mem  :reset  :help  :quit  :exit")
        return True
    print(f"  Unknown command: {cmd}  (try :help)")
    return True


def run_repl() -> None:
    """Run the interactive EmojiASM REPL."""
    try:
        import readline  # noqa: F401 — enables history on supported platforms
    except ImportError:
        pass

    print("EmojiASM REPL  (:help for opcodes, :quit to exit)")

    stack: list = []
    memory: dict = {}

    while True:
        try:
            line = input("emoji> ").strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\n  (KeyboardInterrupt — use :quit to exit)")
            continue

        if not line:
            continue

        if line.startswith(":"):
            should_continue = _handle_meta(line, {"stack": stack, "memory": memory})
            if not should_continue:
                break
            continue

        try:
            prog = _make_single_instruction_program(line)
            vm = VM(prog)
            # Share persistent stack and memory references
            vm.stack = stack
            vm.memory = memory
            vm._exec_function(prog.entry_point)
            # Reset transient state so next instruction starts clean
            vm.halted = False
            vm.call_stack = []
            vm.steps = 0
        except (ParseError, VMError) as e:
            print(e)
            continue

        print(f"stack: {stack}")
