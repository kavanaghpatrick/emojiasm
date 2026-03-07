---
spec: developer-experience
phase: requirements
created: 2026-03-07
generated: auto
---

# Requirements: Developer Experience Improvements

## Summary

Improve EmojiASM's developer experience through three areas: richer error messages with context, an interactive REPL, and syntax highlighting for VS Code and Vim.

## User Stories

### US-1: Grapheme-safe error truncation
As a developer debugging a parse error, I want the "unknown instruction" message to show a complete emoji rather than a sliced codepoint so that the error is readable in my terminal.

**Acceptance Criteria**:
- AC-1.1: `ParseError` for an unknown instruction starting with a multi-byte emoji never produces a replacement character (U+FFFD) or truncated codepoint in the message.
- AC-1.2: The truncated preview ends on a grapheme-cluster boundary at or before 10 grapheme clusters.

### US-2: Function context in parse errors
As a developer reading a parse error, I want to see which function the error occurred in so that I can locate it quickly in a multi-function file.

**Acceptance Criteria**:
- AC-2.1: When a parse error occurs inside a named function, the error message includes the function name.
- AC-2.2: When no function is active (top-level parse error), no function name is shown.

### US-3: Source line in VM runtime errors
As a developer debugging a runtime error, I want to see the IP, the source line of the failing instruction, and the function name so that I can find the problem without a debugger.

**Acceptance Criteria**:
- AC-3.1: VMError for any instruction failure includes the source line text from `inst.source`.
- AC-3.2: VMError includes the current function name.
- AC-3.3: Existing `IP=<n>` format is preserved.

### US-4: "Did you mean?" suggestions for unknown opcodes
As a developer who typed the wrong variation selector on an emoji opcode, I want a suggestion of the correct opcode so that I can fix the typo immediately.

**Acceptance Criteria**:
- AC-4.1: When an unknown instruction token closely matches a known opcode, the error message includes a "did you mean: <emoji>?" hint.
- AC-4.2: No suggestion is shown when there is no close match.
- AC-4.3: Suggestion uses `difflib.get_close_matches` or equivalent; no external dependency.

### US-5: Interactive REPL
As a developer experimenting with EmojiASM, I want to type one instruction at a time and see the stack state after each so that I can learn the language interactively.

**Acceptance Criteria**:
- AC-5.1: `emojiasm --repl` launches an interactive prompt.
- AC-5.2: After each instruction the stack is printed: `stack: [...]`.
- AC-5.3: `:mem` prints the current memory dict.
- AC-5.4: `:reset` clears stack and memory.
- AC-5.5: `:help` lists all available opcodes with their emoji.
- AC-5.6: `:quit` and `:exit` terminate the REPL cleanly.
- AC-5.7: Ctrl+D (EOF) exits gracefully (no traceback).
- AC-5.8: Ctrl+C (KeyboardInterrupt) clears the current input line and continues.
- AC-5.9: Parse or runtime errors are printed but do not terminate the REPL.

### US-6: VS Code syntax highlighting
As a VS Code user editing `.emoji` files, I want syntax highlighting that colors opcodes by category, grays out comments, and highlights string literals so that code is easier to read.

**Acceptance Criteria**:
- AC-6.1: Extension associates `.emoji` file extension.
- AC-6.2: Stack opcodes (`📥 📤 📋 🔀 🫴 🔄`) receive a distinct scope.
- AC-6.3: Arithmetic opcodes (`➕ ➖ ✖️ ✖ ➗ 🔢`) receive a distinct scope.
- AC-6.4: Control-flow opcodes (`👉 🤔 😤 📞 📲 🛑`) receive a distinct scope.
- AC-6.5: I/O opcodes (`📢 🖨️ 🖨 💬 🎤 🔟`) receive a distinct scope.
- AC-6.6: `📜`/`🏷️`/`🏷` directives colorized; `💭` comments grayed out.
- AC-6.7: String literals after `💬` highlighted.

### US-7: Vim syntax highlighting
As a Vim user editing `.emoji` files, I want syntax highlighting equivalent to the VS Code extension.

**Acceptance Criteria**:
- AC-7.1: `editors/vim/syntax/emojiasm.vim` exists and defines highlight groups for the same categories as the VS Code extension.
- AC-7.2: File registers `.emoji` extension.

## Functional Requirements

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-1 | Grapheme-aware truncation helper for error preview | Must | US-1 |
| FR-2 | `ParseError` exposes optional `func_name` in message | Must | US-2 |
| FR-3 | `VMError` includes source line and function name | Must | US-3 |
| FR-4 | `_suggest_opcode()` helper using difflib | Must | US-4 |
| FR-5 | `emojiasm/repl.py` module with `run_repl()` | Must | US-5 |
| FR-6 | `--repl` flag in `__main__.py` | Must | US-5 |
| FR-7 | VS Code extension (3 files) | Should | US-6 |
| FR-8 | Vim syntax file | Should | US-7 |
| FR-9 | README section documenting editor setup | Should | US-6, US-7 |

## Non-Functional Requirements

| ID | Requirement | Category |
|----|-------------|----------|
| NFR-1 | No new runtime dependencies (stdlib only) | Dependency |
| NFR-2 | All 298 existing tests continue to pass | Compatibility |
| NFR-3 | REPL exits within 1s of Ctrl+D | Usability |
| NFR-4 | ParseError/VMError changes backward-compatible (keyword args with defaults) | Compatibility |

## Out of Scope

- DAP (Debug Adapter Protocol) integration
- Language Server Protocol (LSP) support
- Emacs/Sublime syntax files
- REPL history persistence (readline history file)
- REPL multi-line input / paste mode

## Dependencies

- `difflib` (stdlib) — opcode suggestions
- `unicodedata` (stdlib) — grapheme truncation
- VS Code 1.74+ (for TextMate grammar support)
</content>
</invoke>