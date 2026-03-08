---
spec: tier1-numeric-ops
phase: research
created: 2026-03-08
generated: auto
---

# Research: tier1-numeric-ops

## Executive Summary

Adding 9 new opcodes (POW, SQRT, SIN, COS, EXP, LOG, ABS, MIN, MAX) plus transpiler support for math constants, random.uniform/gauss, and chained comparisons. All math ops have direct MSL hardware equivalents (`pow()`, `sqrt()`, `sin()`, etc.) making GPU cost near-zero. The existing opcode pipeline pattern (opcodes.py -> parser -> vm.py -> bytecode.py -> vm.metal -> gpu.py -> compiler.py -> disasm.py) is well-established with 37 existing opcodes providing clear templates.

## Codebase Analysis

### Existing Pipeline Pattern (Per-Opcode)

Each opcode touches 7 files in a consistent pattern:

| Layer | File | What to add | Pattern |
|-------|------|-------------|---------|
| 1. Enum | `opcodes.py` | `Op.POW = auto()` in IntEnum | After `Op.RANDOM` (line 43) |
| 2. Emoji map | `opcodes.py` | `"🔋": Op.POW` in EMOJI_TO_OP | After `🎲` (line 87) |
| 3. VM dispatch | `vm.py` | `case Op.POW:` match arm | After `Op.RANDOM` (line 286) |
| 4. Bytecode | `bytecode.py` | `Op.POW: 0x61` in OP_MAP, entry in _STACK_EFFECTS | After `Op.RANDOM: 0x60` |
| 5. Metal kernel | `metal/vm.metal` | `case OP_POW:` switch arm + constant | After `OP_RANDOM` section |
| 6. GPU glue | `gpu.py` | `"POW": 0x61` in GPU_OPCODES | After `"RANDOM"` |
| 7. C compiler | `compiler.py` | `elif op == Op.POW:` in _emit_inst | After `Op.RANDOM` (line 309) |
| 8. Disasm | `disasm.py` | Automatic via OP_TO_EMOJI reverse map | No change needed |

### Current Opcode Allocation

Bytecode ranges currently used (from `bytecode.py` OP_MAP):
- `0x01-0x06`: Stack ops (PUSH, POP, DUP, SWAP, OVER, ROT)
- `0x10-0x14`: Arithmetic (ADD, SUB, MUL, DIV, MOD)
- `0x20-0x25`: Comparison/Logic (EQ, LT, GT, AND, OR, NOT)
- `0x30-0x36`: Control flow (JMP, JZ, JNZ, CALL, RET, HALT, NOP)
- `0x40-0x41`: Memory (STORE, LOAD)
- `0x50-0x51`: I/O (PRINT, PRINTLN)
- `0x60`: Random (RANDOM)

**Proposed allocation for new ops:**
- `0x15`: POW (extends arithmetic range)
- `0x16-0x1D`: SQRT, SIN, COS, EXP, LOG, ABS, MIN, MAX (math functions in arithmetic range)

### Current Emoji Usage (37 opcodes, some with variants)

Used: 📥📤➕➖✖️✖➗🔢📢🖨️🖨💬📋🔀🫴🔄👉🤔😤🟰📏📐🤝🤙🚫💾📂📞📲🎤🔟🛑💤🧵✂️✂🔍🔁🔤🎲

**Proposed emoji for new opcodes:**

| Opcode | Emoji | Rationale |
|--------|-------|-----------|
| POW | `🔋` | Power/battery = power |
| SQRT | `√` (or `🌱`) | `🌱` root/sprout for square root |
| SIN | `📈` | Sine wave → chart going up |
| COS | `📉` | Cosine wave → chart going down |
| EXP | `🚀` | Exponential growth → rocket |
| LOG | `📓` | Log → logbook/notebook |
| ABS | `📐` CONFLICT → `💪` | Absolute value → strength/magnitude |
| MIN | `⬇️` | Minimum → down arrow |
| MAX | `⬆️` | Maximum → up arrow |

Note: `📐` is already used for CMP_GT. Using `💪` for ABS instead.

### Transpiler Current State

- `visit_BinOp`: handles +, -, *, //, %, explicit error for `**` (ast.Pow) at line 463-467
- `visit_Call`: handles `print()` and `random.random()` (lines 537-600)
- `visit_Compare`: explicit rejection of chained comparisons at line 497-501
- `visit_Import`/`visit_ImportFrom`: allows `random` and `math` modules (lines 385-408)
- `_BINOP_MAP`: maps ast operators to Op enum values

### KB Findings (Key)

- **KB #1**: VM dispatches via match/case chain — new ops add new arms
- **KB #22**: Currently 8 opcodes take args (PUSH, JMP, JZ, JNZ, CALL, STORE, LOAD, PRINTS). None of new math ops need args — all are stack-only
- **KB #23**: 31 opcodes across 6 categories — adding 9 more for math
- **KB #21**: Variation selectors on some emoji (✖️/✖, ✂️/✂) — new emoji should be checked for variants
- **KB #129**: MSL uses float (32-bit) vs C compiler double — math functions differ in precision
- **KB #16**: Numeric-only compiler path uses `double _stk[4096]` — new math ops fit numeric-only path
- **KB #87**: MSL has no goto — C compiler uses goto for labels, fine for math ops which are inline
- **KB #102**: Full stack-based VM can run as Metal compute kernel with switch dispatch

### MSL Native Functions Available

All target math functions have direct MSL equivalents (from `<metal_stdlib>`):
- `pow(float, float)` — power
- `sqrt(float)` — square root
- `sin(float)`, `cos(float)` — trig
- `exp(float)`, `log(float)` — exponential/natural log
- `abs(float)` — absolute value (also `fabs()`)
- `min(float, float)`, `max(float, float)` — min/max

C standard library equivalents (for compiler.py): `pow()`, `sqrt()`, `sin()`, `cos()`, `exp()`, `log()`, `fabs()`, `fmin()`, `fmax()` — require `#include <math.h>`.

### RANDOM Implementation Reference

Current `RANDOM` implementation for extending to uniform/gauss:
- VM (line 285-286): `self._push(random.random())`
- Metal kernel (lines 610-621): Uses Philox-4x32-10 PRNG via `philox_random(rng)`
- C compiler (line 309): `PUSH_N((double)rand() / (double)RAND_MAX);`
- Transpiler (lines 544-560): Handles `random.random()` as attribute call or bare import

`random.uniform(a, b)` = `a + (b-a) * random()` — no new opcode needed, transpiler inlines
`random.gauss(mu, sigma)` = Box-Muller: `mu + sigma * sqrt(-2*ln(u1)) * cos(2*pi*u2)` — needs SQRT, LOG, COS, or inline expansion

### Chained Comparisons

Current: `visit_Compare` raises `TranspileError` for `len(node.ops) > 1`.
Strategy from issue: `a < b < c` compiles to:
1. visit a
2. visit b
3. DUP (save b for second comparison)
4. ROT (bring a to top: stack is now [b_copy, a, b])
5. CMP_LT (compare a < b: stack is [b_copy, result1])
6. SWAP (bring b_copy to top: stack is [result1, b_copy])
7. visit c (stack is [result1, b_copy, c])
8. CMP_LT (compare b < c: stack is [result1, result2])
9. AND (combine: stack is [final_result])

This generalizes to N comparisons by repeating the pattern.

## Feasibility Assessment

| Aspect | Assessment | Notes |
|--------|------------|-------|
| Technical Viability | High | All ops have direct MSL/C equivalents. Pipeline pattern well-established. |
| Effort Estimate | M | 9 new opcodes x 7 files + transpiler changes + tests |
| Risk Level | Low | No architectural changes. Additive-only modifications. |

## Recommendations

1. Add `#include <math.h>` to C compiler numeric preamble
2. New opcodes are all stack-only (no arg) — no OPS_WITH_ARG changes needed
3. MIN/MAX are binary (pop 2, push 1); all others are unary (pop 1, push 1) except POW (pop 2, push 1)
4. Transpiler should inline uniform/gauss using existing + new opcodes rather than adding dedicated opcodes
5. Use variation-selector-free emoji to avoid the ✖️/✖ dual-mapping issue
