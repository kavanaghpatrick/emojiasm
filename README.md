# EmojiASM 🧬

**Assembly language made of pure emoji. No ASCII keywords. Just vibes.**

```
📜 🏠
  💬 "Hello, World! 🌍"
  📢
  🛑
```

> *What if `MOV EAX, 1` was `📥 1` instead?*

EmojiASM is a stack-based assembly language and virtual machine where every opcode, label, function name, memory address, and comment is an emoji. It's a real, working assembler — just not a serious one.

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/patrickkavanagh/emojiasm.git
cd emojiasm
pip install -e .

# Run your first program
emojiasm examples/hello.emoji       # Hello, World! 🌍
emojiasm examples/fibonacci.emoji   # First 20 Fibonacci numbers
emojiasm examples/fizzbuzz.emoji    # FizzBuzz, obviously
emojiasm examples/functions.emoji   # Function calls
```

Or run without installing:

```bash
python3 -m emojiasm examples/hello.emoji
```

---

## The Instruction Set

### Stack Operations

| Emoji | Name | What it does |
|:-----:|------|-------------|
| 📥 | PUSH | Push a value onto the stack |
| 📤 | POP | Discard the top value |
| 📋 | DUP | Duplicate the top value |
| 🔀 | SWAP | Swap the top two values |
| 🫴 | OVER | Copy the second value to top |
| 🔄 | ROT | Rotate the top three values |

### Arithmetic

| Emoji | Name | What it does |
|:-----:|------|-------------|
| ➕ | ADD | Add top two (or concatenate strings!) |
| ➖ | SUB | Subtract |
| ✖️ | MUL | Multiply |
| ➗ | DIV | Integer divide |
| 🔢 | MOD | Modulo |

### Comparison & Logic

| Emoji | Name | What it does |
|:-----:|------|-------------|
| 🟰 | CMP_EQ | Push `1` if equal, `0` if not |
| 📏 | CMP_LT | Push `1` if less than |
| 📐 | CMP_GT | Push `1` if greater than |
| 🤝 | AND | Logical AND |
| 🤙 | OR | Logical OR |
| 🚫 | NOT | Logical NOT |

### Control Flow

| Emoji | Name | What it does |
|:-----:|------|-------------|
| 👉 | JMP | Unconditional jump to label |
| 🤔 | JZ | Jump if top of stack is zero |
| 😤 | JNZ | Jump if top of stack is NOT zero |
| 📞 | CALL | Call a function |
| 📲 | RET | Return from function |
| 🛑 | HALT | Stop the program |
| 💤 | NOP | Do absolutely nothing |

### I/O

| Emoji | Name | What it does |
|:-----:|------|-------------|
| 📢 | PRINT | Print top of stack (no newline) |
| 🖨️ | PRINTLN | Print top of stack + newline |
| 💬 | PRINTS | Push a string literal onto the stack |
| 🎤 | INPUT | Read a line of text input |
| 🔟 | INPUT_NUM | Read a number from input |

### Memory

| Emoji | Name | What it does |
|:-----:|------|-------------|
| 💾 | STORE | Store top of stack to a named cell |
| 📂 | LOAD | Load from a named cell onto stack |

### Directives

| Emoji | Purpose |
|:-----:|---------|
| 📜 | Define a function (default entry point: `🏠`) |
| 🏷️ | Define a jump label |
| 💭 | Comment (ignored by assembler) |

---

## Architecture

EmojiASM runs on a **stack-based virtual machine**:

- **Stack** — all computation happens here. Push values, operate, pop results.
- **Named memory** — store/load values by emoji name (`💾 🅰️` → `📂 🅰️`)
- **Functions** — defined with `📜`, called with `📞`, return with `📲`
- **Labels** — defined with `🏷️`, jumped to with `👉`/`🤔`/`😤`
- **Entry point** — the function named `🏠` (or the first function if no `🏠`)

---

## Examples

### Fibonacci Sequence

Prints the first 20 Fibonacci numbers:

```
💭 Fibonacci sequence

📜 🏠
  💬 "Fibonacci: "
  📢

  📥 0
  💾 🅰️
  📥 1
  💾 🅱️
  📥 0
  💾 🔢

🏷️ 🔁
  📂 🔢
  📥 20
  🟰
  😤 🏁

  📂 🅰️
  📢
  💬 " "
  📢

  📂 🅰️
  📂 🅱️
  ➕
  💾 🌡️

  📂 🅱️
  💾 🅰️
  📂 🌡️
  💾 🅱️

  📂 🔢
  📥 1
  ➕
  💾 🔢

  👉 🔁

🏷️ 🏁
  🛑
```

Output: `Fibonacci: 0 1 1 2 3 5 8 13 21 34 55 89 144 233 377 610 987 1597 2584 4181`

### Functions (Square)

```
📜 🏠
  💬 "5 squared = "
  📢
  📥 5
  📞 🔲
  🖨️
  🛑

💭 Square: pops n, pushes n*n
📜 🔲
  📋
  ✖️
  📲
```

Output: `5 squared = 25`

### Number Guessing Game

```
📜 🏠
  📥 7
  💾 🎯

🏷️ 🔁
  💬 "Guess a number (1-10): "
  📢
  🔟

  📋
  📂 🎯
  🟰
  😤 🎉

  💬 "Nope! Try again.\n"
  📢
  📤
  👉 🔁

🏷️ 🎉
  📤
  💬 "🎉 You got it!\n"
  📢
  🛑
```

---

## Tools

### Debug Mode

Trace every instruction with full stack state:

```bash
emojiasm -d examples/hello.emoji
```

```
  🔍 [🏠:0] 💬 "Hello, World! 🌍"  stack=[]
  🔍 [🏠:1] 📢  stack=['Hello, World! 🌍']
  🔍 [🏠:2] 🛑  stack=[]
```

### Disassembler

Round-trip your programs through the disassembler:

```bash
emojiasm --disasm examples/functions.emoji
```

---

## How It Works

1. **Parser** reads `.emoji` source files, tokenizing emoji opcodes and their arguments
2. **Assembler** resolves labels and function references into a program structure
3. **VM** executes the program on a stack machine with named memory, a call stack, and I/O

The VM includes safety limits (max 1M steps, configurable stack size) to catch infinite loops.

---

## Writing EmojiASM

A few tips:

- **Every instruction is one emoji** followed by an optional argument
- **String literals** use quotes: `💬 "hello"` or `📥 "text"`
- **Numbers** are integers or floats: `📥 42`, `📥 3.14`, `📥 0xFF`
- **Memory cells** are emoji names: `💾 🅰️` stores, `📂 🅰️` loads
- **Labels** are emoji names: `🏷️ 🔁` defines, `👉 🔁` jumps
- **Comments** start with 💭 and are ignored
- **Functions** start with `📜 name` and end at the next `📜` or EOF

---

## License

MIT
