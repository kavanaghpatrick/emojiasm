---
spec: developer-experience
phase: research
created: 2026-03-07
generated: auto
---

# Research: Developer Experience Improvements

## Executive Summary

Three self-contained DX features: better error messages (two parse-time fixes + two new enrichments), an interactive REPL, and static editor syntax files. All changes are additive — no existing API surfaces are broken. Effort is medium overall; the REPL is the only net-new module.

## Codebase Analysis

### Existing Patterns

| Pattern | Location | Relevance |
|---------|----------|-----------|
| `ParseError(msg, line_num, line)` | `parser.py:29-33` | Add `func_name` param here |
| `VMError(msg, ip=-1)` | `vm.py:8-10` | Add `source` param |
| `current_func` variable | `parser.py:109` | Already available at line 148 |
| `inst.source` field | `parser.py:13` | Available in every `Instruction` |
| `inst.line_num` field | `parser.py:12` | Same |
| `EMOJI_TO_OP` dict (31 keys) | `opcodes.py:41-75` | Source for "did you mean?" candidates |
| Variation selector pairs | `opcodes.py:46-47, 51-52` | `✖️`/`✖` and `🖨️`/`🖨` both map to same Op |
| argparse in `__main__.py` | `__main__.py:14-25` | Wire `--repl` flag here |
| `VM.stack`, `VM.memory` | `vm.py:16-17` | REPL state inspection |

### Dependencies

- `unicodedata` (stdlib) — sufficient for grapheme-cluster truncation via `\ufe0f` variation-selector detection; no external dep needed.
- `difflib.get_close_matches` (stdlib) — usable for "did you mean?" opcode suggestions.
- No new runtime dependencies required for any of the three features.
- VS Code extension: static JSON/PLIST files, zero runtime deps.
- Vim syntax: static `.vim` file.

### Constraints

- Python >= 3.10 (match/case already used in vm.py).
- Grapheme library (`grapheme` PyPI package) is NOT installed; must use stdlib Unicode primitives.
- Existing 298 tests must pass — changes to `ParseError`/`VMError` signatures must stay backward-compatible (use keyword args with defaults).
- REPL must handle `EOF` (Ctrl+D) and `KeyboardInterrupt` gracefully per spec.
- Editor files are purely static; no build step.

## Feasibility Assessment

| Aspect | Assessment | Notes |
|--------|------------|-------|
| Technical Viability | High | All hooks already exist in parser/VM |
| Effort Estimate | M | ~8-10 focused tasks |
| Risk Level | Low | Additive changes; error classes use defaults |

### Key Risk: ParseError/VMError backward compat
Both classes are instantiated in tests via positional args. Adding new optional params at the end is safe. Changing the `str()` format would break test assertions that match error strings — avoid changing existing format, only extend.

## Recommendations

1. Fix `line[:10]` (parser.py:148) using a grapheme-aware helper — stdlib `unicodedata` + manual VS detection is sufficient.
2. Extend `ParseError.__init__` to accept optional `func_name` kwarg; append to message when present.
3. Extend `VMError.__init__` to accept optional `source` kwarg; append to message when present.
4. Add `_suggest_opcode(token)` helper in `parser.py` using `difflib.get_close_matches` over `EMOJI_TO_OP` keys.
5. Implement `emojiasm/repl.py` as a standalone module; wire via `--repl` in `__main__.py`.
6. Author VS Code extension as three static files under `editors/vscode/`.
7. Author Vim syntax file at `editors/vim/syntax/emojiasm.vim`.
</content>
</invoke>