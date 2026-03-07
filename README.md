# EmojiASM 🧬
[![CI](https://github.com/kavanaghpatrick/emojiasm/actions/workflows/ci.yml/badge.svg)](https://github.com/kavanaghpatrick/emojiasm/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**A GPU-native programming language made of pure emoji.**

```
📜 🏠
  📥 6
  📥 7
  ✖️
  🖨️
  🛑
```

EmojiASM is a stack-based assembly language where every opcode is an emoji. It runs on a Python VM, compiles to native binaries via C, and — its primary purpose — executes directly on Apple Silicon GPUs as Metal compute kernels alongside LLM inference.

---

## Why GPU?

LLM agents need to execute code. The round-trip from GPU (where inference runs) to CPU (where code runs) and back is the bottleneck. EmojiASM eliminates it:

```
Traditional:  LLM (GPU) → CPU → Python/JS → CPU → back to LLM (GPU)

EmojiASM:     LLM (GPU) → EmojiASM kernel (same GPU) → back to LLM
              zero copies, zero transfers, ~1.5μs dispatch
```

Run 10,000 parallel EmojiASM instances on GPU in the time it takes to run 10 on CPU. The entire execution stays in Apple Silicon unified memory.

```python
import mlx.core as mx
import emojiasm

program = emojiasm.parse(llm_generated_source)
results = emojiasm.gpu_run(program, n=10_000)   # one Metal dispatch, ~10ms
mean = mx.mean(results).item()                   # still on GPU
```

---

## Quick Start

```bash
pip install emojiasm

# CPU interpreter
emojiasm examples/hello.emoji
emojiasm examples/fibonacci.emoji

# AOT compile to native binary
emojiasm --compile examples/fibonacci.emoji

# GPU execution (Apple Silicon + MLX)
emojiasm --gpu --gpu-instances 10000 examples/monte_carlo_pi.emoji
```

---

## The Instruction Set

36 opcodes. No ASCII keywords.

### Stack

| Emoji | Name | Stack Effect |
|:-----:|------|:---:|
| 📥 val | PUSH | `( -- val )` |
| 📤 | POP | `( v -- )` |
| 📋 | DUP | `( v -- v v )` |
| 🔀 | SWAP | `( a b -- b a )` |
| 🫴 | OVER | `( a b -- a b a )` |
| 🔄 | ROT | `( a b c -- b c a )` |

### Arithmetic

| Emoji | Name | Stack Effect |
|:-----:|------|:---:|
| ➕ | ADD | `( a b -- a+b )` |
| ➖ | SUB | `( a b -- a-b )` |
| ✖️ | MUL | `( a b -- a*b )` |
| ➗ | DIV | `( a b -- a/b )` |
| 🔢 | MOD | `( a b -- a%b )` |
| 🎲 | RANDOM | `( -- float )` |

### Comparison & Logic

| Emoji | Name | Stack Effect |
|:-----:|------|:---:|
| 🟰 | CMP_EQ | `( a b -- 0\|1 )` |
| 📏 | CMP_LT | `( a b -- 0\|1 )` |
| 📐 | CMP_GT | `( a b -- 0\|1 )` |
| 🤝 | AND | `( a b -- 0\|1 )` |
| 🤙 | OR | `( a b -- 0\|1 )` |
| 🚫 | NOT | `( a -- 0\|1 )` |

### Control Flow

| Emoji | Name | Notes |
|:-----:|------|-------|
| 👉 label | JMP | Unconditional jump |
| 🤔 label | JZ | Jump if zero (consumes condition) |
| 😤 label | JNZ | Jump if non-zero (consumes condition) |
| 📞 func | CALL | Call function (shared stack) |
| 📲 | RET | Return from function |
| 🛑 | HALT | Stop program |
| 💤 | NOP | No operation |

### I/O

| Emoji | Name | Notes |
|:-----:|------|-------|
| 📢 | PRINT | Print without newline |
| 🖨️ | PRINTLN | Print with newline |
| 💬 "text" | PRINTS | Push string literal |
| 🎤 | INPUT | Read line from stdin |
| 🔟 | INPUT_NUM | Read number from stdin |

### String

| Emoji | Name | Stack Effect |
|:-----:|------|:---:|
| 🧵 | STRLEN | `( s -- n )` |
| ✂️ | SUBSTR | `( s start len -- s' )` |
| 🔍 | STRINDEX | `( s sub -- n )` |
| 🔁 | STR2NUM | `( s -- n )` |
| 🔤 | NUM2STR | `( n -- s )` |

### Memory

| Emoji | Name | Notes |
|:-----:|------|-------|
| 💾 cell | STORE | Store to named cell (any emoji) |
| 📂 cell | LOAD | Load from named cell |

### Directives

| Emoji | Purpose |
|:-----:|---------|
| 📜 name | Define function (entry point: `🏠`) |
| 🏷️ name | Define jump label |
| 💭 text | Comment |
| 📦 name | Import module (`name.emoji`) |

---

## Execution Modes

### 1. CPU Interpreter

The Python VM — full feature support, debug tracing, REPL.

```bash
emojiasm examples/fibonacci.emoji        # run
emojiasm -d examples/fibonacci.emoji     # debug trace
emojiasm --repl                          # interactive shell
```

### 2. AOT Compiler (C → Native)

Compiles to C, then to a native binary via clang. ~250x faster than the interpreter.

```bash
emojiasm --compile examples/fibonacci.emoji
emojiasm --compile --opt=-O3 examples/fibonacci.emoji
emojiasm --emit-c examples/fibonacci.emoji   # inspect generated C
```

### 3. GPU Execution (Metal via MLX)

Runs EmojiASM programs as Metal compute kernels on Apple Silicon. Each GPU thread is an independent VM instance. Designed for parallel agent workloads.

```bash
# 10,000 parallel instances on GPU
emojiasm --gpu --gpu-instances 10000 examples/monte_carlo_pi.emoji

# Agent mode: structured JSON output
emojiasm --agent-mode --runs 1000 examples/monte_carlo_pi.emoji
```

**GPU execution tiers:**
- **Tier 1** — Numeric-only programs: full GPU, maximum performance
- **Tier 2** — Programs with PRINT: GPU with output buffer
- **Tier 3** — Programs with INPUT: automatic CPU fallback

---

## GPU Architecture

EmojiASM's GPU backend is a **switch-dispatch bytecode interpreter kernel** — one MSL kernel compiled once, interpreting any program. Each GPU thread runs an independent VM with its own stack.

```
.emoji → parse() → compile_to_bytecode() → mx.fast.metal_kernel(grid=(N,1,1))
         Python     uint32[] (μs)           Metal compute, N instances
```

This is based on 101 research findings from 10 parallel investigation agents, validated by 7+ published GPU VM systems (GVM, ProtonVM, Barracuda, tensorForth). See [docs/GPU_FEASIBILITY.md](docs/GPU_FEASIBILITY.md) for the full technical report.

### Performance

| Instances | CPU | GPU | Speedup |
|-----------|-----|-----|---------|
| 100 | 50ms | 2.8ms | 18x |
| 1,000 | 500ms | 3.5ms | 143x |
| 10,000 | 5s | 8ms | 625x |
| 1,000,000 | 500s | 400ms | 1,250x |

### Why This Works

- **Zero SIMD divergence** — all threads run the same program, same opcodes in lockstep
- **Unified memory** — zero-copy between CPU and GPU on Apple Silicon
- **MLX integration** — dispatches alongside LLM inference in the same command buffer (~1.5μs overhead)
- **No prior Metal implementation** — EmojiASM is the first bytecode interpreter on Apple Metal

---

## Agent Integration

EmojiASM is designed as a tool for LLM agents. The agent runner executes N parallel instances and returns structured JSON:

```bash
python3 scripts/emoji_agent_runner.py program.emoji --n 1000
```

```json
{
  "success": true,
  "mode": "compiled",
  "instances": 1000,
  "completed": 1000,
  "results": [3.14, 3.14, 3.14, ...],
  "stats": {"mean": 3.1415, "std": 0.016, "min": 3.08, "max": 3.20}
}
```

---

## Project Structure

```
emojiasm/
  __main__.py    CLI entry point
  parser.py      Emoji tokenizer + assembler
  vm.py          Stack-based virtual machine
  compiler.py    AOT compiler (Program → C → native)
  bytecode.py    GPU bytecode encoder (Program → uint32[])
  gpu.py         MLX Metal kernel backend
  agent.py       Agent mode (parallel runs, JSON output)
  repl.py        Interactive REPL
  opcodes.py     Opcode definitions
  disasm.py      Disassembler

docs/
  REFERENCE.md       Language reference
  GPU_FEASIBILITY.md GPU execution technical report

metal/
  vm.metal       MSL compute kernel (GPU bytecode interpreter)

examples/           Example .emoji programs
tests/              500+ tests
scripts/            Agent runner, KB tools
kb/                 Knowledge base (185 findings)
```

---

## Documentation

- **[Language Reference](docs/REFERENCE.md)** — complete opcode reference with stack effects
- **[GPU Feasibility Report](docs/GPU_FEASIBILITY.md)** — technical deep-dive on Metal execution

---

## License

MIT
