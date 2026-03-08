# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable)
pip install -e .

# Run a program (CPU)
emojiasm examples/hello.emoji
python3 -m emojiasm examples/hello.emoji

# Debug trace (prints to stderr)
emojiasm -d examples/fibonacci.emoji

# Disassemble only
emojiasm --disasm examples/functions.emoji

# GPU execution (Apple Silicon + MLX)
emojiasm --gpu examples/monte_carlo_pi.emoji
emojiasm --gpu --gpu-instances 10000 examples/monte_carlo_pi.emoji

# Python transpiler
emojiasm --from-python examples_py/monte_carlo_pi.py       # transpile + run
emojiasm --transpile examples_py/fibonacci.py               # emit EmojiASM source
emojiasm --from-python script.py --gpu --gpu-instances 1000 # transpile + GPU

# Run tests
pytest

# Run a single test
pytest tests/test_emojiasm.py::test_function_call
pytest tests/test_transpiler.py -v
pytest tests/test_bytecode.py -v
```

## Architecture

EmojiASM has two execution paths: CPU (Python VM) and GPU (Metal via MLX). A Python transpiler enables writing Python and executing as EmojiASM.

### CPU Pipeline

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

**3. Compiler (`emojiasm/compiler.py`)** — AOT compiles to C, then native binary via clang.

**4. Disassembler (`emojiasm/disasm.py`)** — Reconstructs source from a parsed `Program`, using `OP_TO_EMOJI` (reverse of `EMOJI_TO_OP`).

### GPU Pipeline

**5. Bytecode Compiler (`emojiasm/bytecode.py`)** — Encodes `Program` → packed `uint32[]` + float constant pool.
- Instruction format: `[31:24]` opcode (8 bits), `[23:0]` operand (24 bits).
- `compile_to_bytecode(program) → GpuProgram` flattens functions, resolves jumps/calls to bytecode offsets, deduplicates float constants into a pool, maps memory cell emoji names to integer indices.
- `gpu_tier(program) → int` classifies: Tier 1 (numeric-only), Tier 2 (PRINT/PRINTLN), Tier 3 (INPUT/strings → CPU fallback).
- `_build_string_table()` extracts PRINTS literals for Tier 2 output buffer.

**6. MSL Kernel (`emojiasm/metal/vm.metal`)** — Metal compute kernel: switch-dispatch bytecode interpreter.
- Each GPU thread runs one independent VM with its own stack (128 entries in device memory), call stack (16 entries thread-local), and memory cells (32 thread-local).
- Philox-4x32-10 PRNG for RANDOM opcode (seeded by thread ID).
- Tier 2 output buffer: per-thread `OutputEntry` slots with atomic append for PRINT/PRINTLN.
- Status codes: 0=ok, 1=error, 2=div-by-zero, 3=timeout.

**7. MLX Backend (`emojiasm/gpu.py`)** — Dispatches kernel via `mx.fast.metal_kernel()`.
- `gpu_run(program, n, max_steps, stack_depth) → dict` — main GPU execution API.
- `_split_kernel_source()` splits vm.metal into header + body, patches scalar access for MLX API.
- `_get_kernel()` — cached kernel creation (compiled once, reused).
- `_reconstruct_output()` — reassembles per-thread output from GPU buffer for Tier 2 programs.
- `gpu_available()` — safe MLX/Metal check, `run_auto()` — auto GPU/CPU routing.

**8. Inference Integration (`emojiasm/inference.py`)** — LLM-facing API.
- `EmojiASMTool` — execute(), execute_python(), validate(), as_tool_spec(), handle_tool_call().
- Auto-routes GPU when n>=256, MLX available, and tier<=2; CPU otherwise.

### Python Transpiler

**9. Transpiler (`emojiasm/transpiler.py`)** — Compiles Python → `Program` via `ast.NodeVisitor`.
- `transpile(source) → Program` — main entry point, produces same `Program` as `parse()`.
- `transpile_to_source(source) → str` — transpile + disassemble to EmojiASM source text.
- `PythonTranspiler` — AST visitor with `VarManager` (variables → emoji memory cells) and `LabelGenerator` (control flow labels).
- Supported: int/float/bool, arithmetic, comparisons, `and`/`or`/`not`, `if`/`elif`/`else`, `while`, `for x in range()`, `break`/`continue`, `def`/`return` (including recursion), `print()`, `random.random()`.
- Key design: saves/restores local variables around function calls (memory cells are global, so recursive calls would clobber parent's locals without this). Excludes `__retval__` temp cell from save set.
- CLI: `--from-python FILE` (transpile + run), `--transpile FILE` (emit EmojiASM source).

### Opcode Definitions

**`emojiasm/opcodes.py`** — Single source of truth for the emoji→`Op` mapping (37 unique ops, 40 emoji mappings). Some opcodes have two emoji variants (e.g., `✖️`/`✖` for MUL) to handle variation selectors. `OPS_WITH_ARG` controls which opcodes require an argument during parsing. `bytecode.py:OP_MAP` maps `Op` → GPU hex codes.

## Knowledge Base

Project KB lives in `kb/data/emojiasm_kb.db` (SQLite, 185 findings including 101 GPU-specific). Query via `scripts/kb`:

```bash
scripts/kb stats                        # overview
scripts/kb search "dispatch"            # BM25 full-text search
scripts/kb skill language-ref           # all developer reference findings
scripts/kb topic gotcha                 # common mistakes
scripts/kb detail <id>                  # full finding with evidence
```

Skills: `vm`, `parser`, `compiler`, `opcodes`, `performance`, `assemblers`, `esoteric`, `tooling`, `language-ref`

KB schema uses `claim` column (not `title`).

Human-readable language reference: `docs/REFERENCE.md`

## Testing Pattern

715 tests across multiple files. CPU tests in `tests/test_emojiasm.py` use an inline `run()` helper that calls `parse()` then `VM.run()` and returns `output_buffer`. Assert against `"".join(out)` or `.strip()` it. Transpiler tests in `tests/test_transpiler.py` use `run_py()` helper that calls `transpile()` then `VM.run()`.

GPU tests use `@requires_mlx` decorator (skip if MLX not installed). Bytecode/kernel tests validate opcode maps, source structure, and encoding without needing a GPU.
