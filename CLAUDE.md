# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable)
pip install -e .

# Run a program
emojiasm examples/hello.emoji
python3 -m emojiasm examples/hello.emoji

# Debug trace (prints to stderr)
emojiasm -d examples/fibonacci.emoji

# Disassemble only
emojiasm --disasm examples/functions.emoji

# Run tests
pytest

# Run a single test
pytest tests/test_emojiasm.py::test_function_call
```

## Architecture

EmojiASM is a stack-based VM with a three-stage pipeline:

**1. Parser (`emojiasm/parser.py`)** — Tokenizes `.emoji` source into a `Program` dataclass.
- `Program` holds a `dict[str, Function]` and an `entry_point` (defaults to `🏠`).
- `Function` holds a list of `Instruction`s and a `labels` dict mapping emoji names to instruction indices (resolved at parse time).
- `Instruction` holds an `Op` enum, an optional `arg`, and source location info.
- The parser uses string prefix matching against `EMOJI_TO_OP` to identify opcodes — order matters for multi-codepoint emoji variants (e.g., `✖️` vs `✖`).
- Directives (`📜` func, `🏷️` label, `💭` comment) are structural and not emitted as instructions.

**2. VM (`emojiasm/vm.py`)** — Executes a `Program` on a stack machine.
- Core state: `stack` (list), `memory` (dict keyed by emoji strings), `call_stack` (list of `(func_name, return_ip)` tuples).
- `CALL` uses Python recursion via `_exec_function` — the Python call stack mirrors the EmojiASM call stack.
- Safety limits: `max_steps=1_000_000` (infinite loop guard), `max_stack=4096`.
- `ADD` doubles as string concatenation when either operand is a string.
- `DIV` uses integer division (`//`) when both operands are `int`, float division otherwise.
- Output goes to both `stdout` and `self.output_buffer` (used by tests to capture output).

**3. Disassembler (`emojiasm/disasm.py`)** — Reconstructs source from a parsed `Program`, using `OP_TO_EMOJI` (reverse of `EMOJI_TO_OP`).

**Opcode definitions (`emojiasm/opcodes.py`)** — Single source of truth for the emoji→`Op` mapping. Some opcodes have two emoji variants (e.g., `✖️`/`✖` for MUL, `🖨️`/`🖨` for PRINTLN) to handle variation selectors. `OPS_WITH_ARG` controls which opcodes require an argument during parsing.

## Knowledge Base

Project KB lives in `kb/data/emojiasm_kb.db` (SQLite). Query it via `scripts/kb`:

```bash
scripts/kb stats                        # overview
scripts/kb search "dispatch"            # BM25 full-text search
scripts/kb skill language-ref           # all developer reference findings
scripts/kb topic gotcha                 # common mistakes
scripts/kb detail <id>                  # full finding with evidence
```

Skills: `vm`, `parser`, `compiler`, `opcodes`, `performance`, `assemblers`, `esoteric`, `tooling`, `language-ref`

The Claude commands `/kb` and `/kb-research` wrap the CLI for interactive querying and web research.

Human-readable language reference: `docs/REFERENCE.md`

## Testing Pattern

Tests in `tests/test_emojiasm.py` use an inline `run()` helper that calls `parse()` then `VM.run()` and returns `output_buffer`. Assert against `"".join(out)` or `.strip()` it. Source strings use `\n` for line breaks or triple-quoted multiline strings.
