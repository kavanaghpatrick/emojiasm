# EmojiASM Language Reference

> Stack notation (Forth-style): `( before -- after )`
> `n` = number · `i` = integer · `s` = string · `v` = any value · `0|1` = boolean integer

---

## Directives

Structural — not instructions, not on the stack.

| Directive | Purpose |
|:---:|---|
| `📜 name` | Define a function named `name` (emoji). Entry point is `🏠` by default. |
| `🏷️ name` | Define a jump label at this position in the current function. |
| `💭 text` | Comment — ignored by the parser. |
| `📦 name` | Import module — loads `name.emoji` and merges its functions into the current program. Resolves relative to the importing file's directory, then `EMOJIASM_PATH`. Circular imports raise a parse error. |

---

## Instruction Set

### Stack

| Emoji | Name | Stack effect | Notes |
|:---:|---|:---:|---|
| `📥 val` | PUSH | `( -- val )` | val: integer, `0xFF` hex, `0b101` binary, float, `"string"` |
| `📤` | POP | `( v -- )` | Discard top |
| `📋` | DUP | `( v -- v v )` | Copy top |
| `🔀` | SWAP | `( a b -- b a )` | Swap top two |
| `🫴` | OVER | `( a b -- a b a )` | Copy second to top |
| `🔄` | ROT | `( a b c -- b c a )` | Rotate top three |

### Arithmetic

| Emoji | Name | Stack effect | Notes |
|:---:|---|:---:|---|
| `➕` | ADD | `( a b -- a+b )` | String concat if either is `s` |
| `➖` | SUB | `( a b -- a-b )` | Numeric only |
| `✖️` | MUL | `( a b -- a*b )` | Also `✖` (no variation selector) |
| `➗` | DIV | `( a b -- a//b\|a/b )` | Floor div for `i//i`, float otherwise. Error on zero. |
| `🔢` | MOD | `( a b -- a%b )` | Integer remainder. Error on zero. |
| `🎲` | RANDOM | `( -- float )` | Push random float in [0.0, 1.0). GPU: Philox-4x32-10 PRNG. |

### Comparison & Logic

All comparison ops consume both operands and push `1` (true) or `0` (false).

| Emoji | Name | Stack effect | Notes |
|:---:|---|:---:|---|
| `🟰` | CMP_EQ | `( a b -- 0\|1 )` | Works on numbers and strings |
| `📏` | CMP_LT | `( a b -- 0\|1 )` | `a < b` — deeper less than top |
| `📐` | CMP_GT | `( a b -- 0\|1 )` | `a > b` — deeper greater than top |
| `🤝` | AND | `( a b -- 0\|1 )` | Python truthiness |
| `🤙` | OR | `( a b -- 0\|1 )` | Python truthiness |
| `🚫` | NOT | `( a -- 0\|1 )` | Unary |

### Control Flow

| Emoji | Name | Stack effect | Notes |
|:---:|---|:---:|---|
| `👉 label` | JMP | `( -- )` | Unconditional jump |
| `🤔 label` | JZ | `( cond -- )` | Jump if cond `== 0`. **Consumes cond.** |
| `😤 label` | JNZ | `( cond -- )` | Jump if cond `!= 0`. **Consumes cond.** |
| `📞 func` | CALL | `( -- )` | Call named function. Stack is shared. |
| `📲` | RET | `( -- )` | Return. Leave result on stack. |
| `🛑` | HALT | `( -- )` | Stop program. |
| `💤` | NOP | `( -- )` | Do nothing. |

> **Labels are function-scoped.** `👉` cannot jump to a label in a different `📜`.

### I/O

| Emoji | Name | Stack effect | Notes |
|:---:|---|:---:|---|
| `📢` | PRINT | `( v -- )` | Print without newline |
| `🖨️` | PRINTLN | `( v -- )` | Print with newline. Also `🖨`. |
| `💬 "text"` | PRINTS | `( -- s )` | **Push** string literal. Does not print. |
| `🎤` | INPUT | `( -- s )` | Read line from stdin |
| `🔟` | INPUT_NUM | `( -- n )` | Read number from stdin. Silently `0` on bad input. |

### String

| Emoji | Name | Stack effect | Notes |
|:---:|---|:---:|---|
| `🧵` | STRLEN | `( s -- n )` | Length of string |
| `✂️` | SUBSTR | `( s start len -- s' )` | Python `s[start:start+len]`. Negative start counts from end. Also `✂`. |
| `🔍` | STRINDEX | `( s sub -- n )` | First index of sub in s. Returns `-1` if not found. |
| `🔁` | STR2NUM | `( s -- n )` | Parse string to int or float. **Error on invalid input.** |
| `🔤` | NUM2STR | `( n -- s )` | Convert number to string. |

### Memory

| Emoji | Name | Stack effect | Notes |
|:---:|---|:---:|---|
| `💾 cell` | STORE | `( v -- )` | Store in named cell (any emoji) |
| `📂 cell` | LOAD | `( -- v )` | Load from cell. **Error if never written.** |

> Memory cells are **global** — visible and writable across all functions.

---

## Patterns & Idioms

### While loop

```
📥 0  💾 🔢         💭 i = 0

🏷️ 🔁              💭 loop start
  📂 🔢  📥 N  🟰  💭 i == N?
  😤 🏁            💭 exit when true
  [body]
  📂 🔢  📥 1  ➕  💾 🔢  💭 i++
  👉 🔁

🏷️ 🏁              💭 loop end
```

### If-then

```
[push condition]
🤔 🏁       💭 skip body if false (0)
[body]
🏷️ 🏁
```

### If-then-else

```
[push condition]
🤔 🔀       💭 jump to else branch if false
[then body]
👉 🏁
🏷️ 🔀       💭 else:
[else body]
🏷️ 🏁
```

### Function with argument and return value

```
📜 🏠
  📥 5      💭 push argument
  📞 🔲     💭 call function
  🖨️        💭 print result
  🛑

💭 Square: ( n -- n*n )
📜 🔲
  📋        💭 DUP: need n twice
  ✖️
  📲
```

### String formatting

```
💬 "Value: "
📂 🔢        💭 push a number
➕           💭 "Value: " + number (auto-convert)
📢
```

### Swap two cells via stack

```
📂 🅰️  📂 🅱️    💭 stack: [a, b]
💾 🅰️            💭 A ← b
💾 🅱️            💭 B ← a
```

---

## Gotchas

**`🤔`/`😤` consume the condition.**
The condition value is always popped. If you need it after the jump, `📋 DUP` it first.

```
📂 🔢
📋           💭 DUP before comparison
📥 10  🟰
😤 🏁        💭 now 🔢 is still on stack for use in body
```

**`💬 PRINTS` pushes; `📢 PRINT` pops.** They are asymmetric.
`💬 "hello"  💬 "world"  📢` prints `world` and leaves `hello` on the stack.

**`📂 LOAD` on an uninitialised cell crashes.** Always `💾 STORE` before `📂 LOAD`.

**Labels are function-scoped.** You cannot `👉` from one `📜` function to a label in another.

**Memory is global.** All named cells are shared across every function call on the same VM.

**Variation selectors.** `✖️` and `✖` both work. If you get "Unknown instruction" for a visually correct opcode, the clipboard may have stripped the variation selector. Re-type it.

**Step limit.** Default max is 1,000,000 steps. Long programs need `--max-steps N`.

---

## Debugging

```bash
# Trace every instruction with stack state (to stderr)
emojiasm -d examples/fibonacci.emoji

# Verify the parser understood your source
emojiasm --disasm examples/fibonacci.emoji

# Inspect generated C before compiling
emojiasm --emit-c examples/fibonacci.emoji

# Compile to native and run
emojiasm --compile examples/fibonacci.emoji
emojiasm --compile --opt=-O3 examples/fibonacci.emoji
```

Debug trace format:
```
🔍 [🏠:0] 💬 "Fibonacci: "  stack=[]
🔍 [🏠:1] 📢               stack=['Fibonacci: ']
```

---

## Type System

EmojiASM has three runtime types inherited from Python: **int**, **float**, **str**.

| Literal | Type | Example |
|---|---|---|
| `42`, `-7`, `0xFF`, `0b101` | `int` | `📥 255` |
| `3.14`, `-0.5` | `float` | `📥 3.14` |
| `"text"`, `'text'`, `«text»` | `str` | `📥 "hello"` |

**Type coercion rules:**
- `➕` with any `str` operand → string concatenation (other operand auto-converted)
- `➗` with two `int` operands → floor division (`7 / 2 = 3`). Use `📥 7.0` for float result.
- Comparison between incompatible types (e.g. `int` vs `str`) → Python `TypeError` at runtime
- `🤙 OR` / `🤝 AND` / `🚫 NOT` use Python truthiness: `0`, `0.0`, `""` are falsy

---

## CLI Reference

```
emojiasm <file>                    Run interpreter
emojiasm -d <file>                 Debug trace
emojiasm --disasm <file>           Disassemble (no run)
emojiasm --compile <file>          AOT compile + run (clang -O2)
emojiasm --compile --opt=-O3 <file>  AOT compile with -O3
emojiasm --emit-c <file>           Print generated C
emojiasm --max-steps N <file>      Override step limit (default 1000000)
emojiasm --repl                   Launch interactive REPL
emojiasm --agent-mode <file>      JSON output with tracing
emojiasm --agent-mode --runs 4 <file>  Parallel VM instances
emojiasm --agent-mode --trace-steps 10 <file>  Trace every 10 steps
```

---

## Agent Integration

`scripts/emoji_agent_runner.py` runs N parallel EmojiASM instances and returns structured JSON.
Uses the AOT compiler when `clang` is available; falls back to Python VM automatically.

```
python3 scripts/emoji_agent_runner.py program.emoji            # 1000 runs
python3 scripts/emoji_agent_runner.py program.emoji --n 500    # 500 runs
python3 scripts/emoji_agent_runner.py program.emoji --no-compile --output out.json
```

JSON keys: `success`, `error`, `program`, `mode`, `instances`, `workers`,
`total_time_ms`, `completed`, `failed`, `results` (float list), `stats`, `message`.
