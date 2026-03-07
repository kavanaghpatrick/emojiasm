---
spec: developer-experience
phase: tasks
total_tasks: 12
created: 2026-03-07
generated: auto
---

# Tasks: Developer Experience Improvements

## Phase 1: Make It Work (POC)

Focus: Get each feature working end-to-end. Tests come in Phase 3.

---

### Task 1.1: Grapheme-aware truncation + "did you mean?" in parser

**Goal**: Fix `parser.py:148` — replace `line[:10]` with a grapheme-safe preview; add opcode suggestion.

**Files**: `emojiasm/parser.py`

**Do**:
1. Add `import difflib` and `import unicodedata` at top of `parser.py` (after existing imports).
2. Add helper function `_grapheme_truncate(s: str, n: int = 10) -> str` after the imports:
   - Iterate codepoints; track cluster count (increment only when `unicodedata.combining(ch) == 0` and `unicodedata.category(ch) != 'Mn'` and ch not in variation-selector ranges `\ufe00`–`\ufe0f`).
   - Return first `n` clusters + `"..."` if truncated, else full string.
3. Add helper function `_suggest_opcode(token: str) -> str` after `_grapheme_truncate`:
   - `matches = difflib.get_close_matches(token, list(EMOJI_TO_OP.keys()), n=1, cutoff=0.6)`
   - Return `f" Did you mean: {matches[0]}?"` if matches else `""`.
4. At line 148, replace:
   ```python
   raise ParseError(f"Unknown instruction: {line[:10]}...", line_num, raw_line)
   ```
   with:
   ```python
   preview = _grapheme_truncate(line, 10)
   hint = _suggest_opcode(line.split()[0] if line.split() else line)
   raise ParseError(
       f"Unknown instruction: {preview}{hint}",
       line_num,
       raw_line,
       func_name=current_func.name if current_func else "",
   )
   ```

**Done when**: `python3 -c "from emojiasm.parser import parse; parse('📜 🏠\n  ❓ bad')"` raises a `ParseError` whose message does not contain `?` replacement chars and does contain `"Did you mean"` OR a clean "Unknown instruction" message.

**Verify**:
```bash
cd /Users/patrickkavanagh/emojiasm && python3 -c "
from emojiasm.parser import ParseError, parse
try:
    parse('📜 🏠\n  ✖bad')
except ParseError as e:
    print(str(e))
"
```

**Commit**: `fix(parser): grapheme-safe truncation and did-you-mean suggestions in ParseError`

_Requirements: FR-1, FR-4, AC-1.1, AC-1.2, AC-4.1_
_Design: _grapheme_truncate, _suggest_opcode_

---

### Task 1.2: Add func_name to ParseError

**Goal**: `ParseError` shows the enclosing function name when one is active.

**Files**: `emojiasm/parser.py`

**Do**:
1. Update `ParseError.__init__` signature to:
   ```python
   def __init__(self, message: str, line_num: int = 0, line: str = "", func_name: str = ""):
   ```
2. Store `self.func_name = func_name`.
3. Update `super().__init__` to:
   ```python
   loc = f"[{func_name}] " if func_name else ""
   super().__init__(f"💥 Line {line_num}: {loc}{message}\n   → {line}")
   ```
4. Existing call sites (label outside function, label requires name, label directive) do NOT need func_name — they already have the right context or no current_func. Leave them unchanged.

**Done when**: Error for unknown instruction inside a named function shows `[func_name]` in message; error at top level does not.

**Verify**:
```bash
cd /Users/patrickkavanagh/emojiasm && python3 -c "
from emojiasm.parser import ParseError, parse
try:
    parse('📜 myFunc\n  ❓ bad')
except ParseError as e:
    assert '[myFunc]' in str(e), repr(str(e))
    print('PASS:', str(e))
"
```

**Commit**: `feat(parser): include function name in ParseError messages`

_Requirements: FR-2, AC-2.1, AC-2.2_
_Design: ParseError_

---

### Task 1.3: Enrich VMError with source line and function name

**Goal**: VM runtime errors show IP, function name, and failing source line.

**Files**: `emojiasm/vm.py`

**Do**:
1. Update `VMError.__init__` to:
   ```python
   def __init__(self, message: str, ip: int = -1, source: str = "", func_name: str = ""):
       self.ip = ip
       self.source = source
       self.func_name = func_name
       loc = f" in {func_name}" if func_name else ""
       src = f"\n   → {source}" if source else ""
       super().__init__(f"💀 Runtime error at IP={ip}{loc}: {message}{src}")
   ```
2. In `_exec_function`, at every `raise VMError(msg, ip)` call that is inside the `while` loop (i.e., where `inst` and `func_name` are in scope), add `source=inst.source, func_name=func_name`. There are these raise sites inside the loop:
   - `Op.DIV` division by zero
   - `Op.MOD` modulo by zero
   - `Op.OVER` needs 2 elements
   - `Op.ROT` needs 3 elements
   - `Op.LOAD` address not initialized
   - `Op.CALL` function not found
   - The default `case _` unknown opcode
3. Raise sites in `_push`, `_pop`, `_peek`, `_resolve_label` are called from within the loop but don't have `inst` directly — leave them with `ip` only (they are helpers, `ip` is sufficient there). They already have `ip` passed via the loop or not at all.
   - Actually `_push/_pop/_peek` have no `ip` param — leave as-is; enrich only the direct `raise VMError` lines inside `_exec_function`'s match/case block.

**Done when**: A division-by-zero runtime error prints the source emoji line.

**Verify**:
```bash
cd /Users/patrickkavanagh/emojiasm && python3 -c "
from emojiasm.parser import parse
from emojiasm.vm import VM, VMError
try:
    vm = VM(parse('📜 🏠\n  📥 5\n  📥 0\n  ➗\n  🛑'))
    vm.run()
except VMError as e:
    print(str(e))
    assert 'in 🏠' in str(e)
    assert '➗' in str(e)
    print('PASS')
"
```

**Commit**: `feat(vm): include source line and function name in VMError messages`

_Requirements: FR-3, AC-3.1, AC-3.2, AC-3.3_
_Design: VMError_

---

### Task 1.4: Implement REPL module

**Goal**: `emojiasm/repl.py` with full `run_repl()` function.

**Files**: `emojiasm/repl.py` (create)

**Do**: Create `/Users/patrickkavanagh/emojiasm/emojiasm/repl.py` with the following structure:
1. Imports: `sys`, `from .parser import parse, ParseError, EMOJI_TO_OP`, `from .vm import VM, VMError`.
2. `_make_single_instruction_program(line: str)` — wraps `line` in `"📜 🏠\n  {line}"` and calls `parse()`.
3. `_exec_one(vm: VM, line: str) -> None` — calls `_make_single_instruction_program`, extracts `instructions[0]` from `functions["🏠"]`, then calls `vm._exec_function("🏠")` on a minimal program.
   - Simpler approach: instead of calling the private `_exec_function`, create a fresh VM for each instruction that shares the same `stack` and `memory` references. But this gets complex with call stack.
   - **Simplest working approach**: Parse the line into a single-instruction program. Create a temporary VM with shared `stack` and `memory`. Call `vm_temp._exec_function(entry)`. After each call, sync `stack` and `memory` back to the REPL's persistent state object.
   - Even simpler: maintain a mutable state dict `{"stack": [], "memory": {}}` and reconstruct a VM with those references each call. Since `VM.__init__` assigns `self.stack = []` and `self.memory = {}` directly, subclass or patch after init.
   - **Recommended**: After `VM.__init__`, replace `vm_temp.stack` and `vm_temp.memory` with REPL's references before calling `_exec_function`. This is a two-line patch.
4. Meta command handler `_handle_meta(cmd: str, state: dict) -> bool`:
   - `:mem` — `print(state["memory"])`
   - `:reset` — clear `state["stack"]` and `state["memory"]`
   - `:help` — print all `EMOJI_TO_OP` keys with op names
   - `:quit` / `:exit` — return `False` (signals exit)
   - Unknown `:` cmd — print error, return `True`
5. `run_repl()`:
   ```python
   try:
       import readline  # enables history on platforms that support it
   except ImportError:
       pass
   print("EmojiASM REPL  (:help for opcodes, :quit to exit)")
   stack = []
   memory = {}
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
           vm.stack = stack
           vm.memory = memory
           vm._exec_function(prog.entry_point)
       except (ParseError, VMError) as e:
           print(e)
           continue
       print(f"stack: {stack}")
   ```

**Done when**: `echo ':quit' | python3 -m emojiasm --repl` exits cleanly (once wired in task 1.5).

**Verify** (after task 1.5):
```bash
cd /Users/patrickkavanagh/emojiasm && echo -e "📥 42\n📥 8\n➕\n:quit" | python3 -m emojiasm --repl
```
Expected: `stack: [42]`, `stack: [42, 8]`, `stack: [50]`, then exit.

**Commit**: `feat(repl): implement interactive REPL module`

_Requirements: FR-5, AC-5.1–AC-5.9_
_Design: REPL_

---

### Task 1.5: Wire --repl flag in __main__.py

**Goal**: `emojiasm --repl` launches the REPL; `file` positional becomes optional.

**Files**: `emojiasm/__main__.py`

**Do**:
1. Change `ap.add_argument("file", ...)` to `ap.add_argument("file", nargs="?", default=None, help="Source file (.emoji)")`.
2. Add `ap.add_argument("--repl", action="store_true", help="Launch interactive REPL")`.
3. Add import: `from .repl import run_repl`.
4. After `args = ap.parse_args()`, add at the top of `main()`:
   ```python
   if args.repl:
       run_repl()
       return
   ```
5. Add a guard for missing `file` when not in REPL mode:
   ```python
   if args.file is None:
       ap.error("the following arguments are required: file (or use --repl)")
   ```

**Done when**: `echo ':quit' | python3 -m emojiasm --repl` exits with code 0.

**Verify**:
```bash
cd /Users/patrickkavanagh/emojiasm && echo ':quit' | python3 -m emojiasm --repl; echo "exit: $?"
```

**Commit**: `feat(cli): add --repl flag to launch interactive REPL`

_Requirements: FR-6, AC-5.1_
_Design: __main__.py changes_

---

### Task 1.6: POC Checkpoint

**Goal**: Verify all three error enrichments and REPL work end-to-end.

**Do**:
1. Run existing test suite — must pass.
2. Manually test each error enrichment:
   - Unknown instruction in a function shows `[funcName]`.
   - Div-by-zero shows source line.
   - Near-miss opcode shows "Did you mean?".
3. Manually test REPL: push, add, `:mem`, `:reset`, `:help`, Ctrl+D.

**Verify**:
```bash
cd /Users/patrickkavanagh/emojiasm && python3 -m pytest tests/ -q
```

**Done when**: All existing tests pass, manual smoke tests pass.

**Commit**: `feat(dx): POC complete — error messages + REPL working`

---

## Phase 2: Refactoring

### Task 2.1: Extract grapheme helper and add type hints

**Goal**: Clean up parser.py additions — proper docstrings, type annotations, edge cases.

**Files**: `emojiasm/parser.py`

**Do**:
1. Add docstring to `_grapheme_truncate` explaining cluster detection logic.
2. Add type annotations: `_grapheme_truncate(s: str, n: int = 10) -> str`.
3. Add type annotation: `_suggest_opcode(token: str) -> str`.
4. Handle empty string edge case in `_grapheme_truncate` (return `""`).
5. Handle empty-line edge case in the `_suggest_opcode` call site (already handled by `line.split()[0] if line.split() else line`).

**Verify**:
```bash
cd /Users/patrickkavanagh/emojiasm && python3 -m pytest tests/ -q && python3 -c "from emojiasm.parser import _grapheme_truncate; assert _grapheme_truncate('') == ''; print('OK')"
```

**Done when**: Type check passes (if project uses mypy), all tests pass.

**Commit**: `refactor(parser): docstrings and type hints for new DX helpers`

---

### Task 2.2: Harden REPL VM state sharing

**Goal**: Ensure REPL handles HALT, RET, and CALL gracefully (these change VM internal state in ways that could confuse the persistent loop).

**Files**: `emojiasm/repl.py`

**Do**:
1. After `vm._exec_function(...)`, reset `vm.halted = False` so the next instruction isn't skipped.
2. Reset `vm.call_stack = []` after each instruction execution so stale call frames don't accumulate.
3. Reset `vm.steps = 0` so the step limit applies per-instruction, not cumulatively.
4. Wrap the `vm._exec_function` call to catch `SystemExit` (in case HALT causes one — it doesn't currently, but defensive).
5. For `:reset`, ensure `stack.clear()` and `memory.clear()` are used (mutates in place) rather than reassigning references, so the VM's reference to the same list/dict stays valid.

**Verify**:
```bash
cd /Users/patrickkavanagh/emojiasm && echo -e "📥 5\n🛑\n📥 10\n:quit" | python3 -m emojiasm --repl
```
Expected: stack shows 5, then HALT is handled, then 10 is pushed fine.

**Commit**: `refactor(repl): harden VM state sharing across instructions`

---

## Phase 3: Testing

### Task 3.1: Tests for error message enrichments

**Goal**: Cover the three parser/VM error enrichments with explicit assertions.

**Files**: `tests/test_errors.py` (create)

**Do**: Create `/Users/patrickkavanagh/emojiasm/tests/test_errors.py` with:

1. `test_grapheme_truncate_basic` — single-byte string, verify no `...` appended when under limit.
2. `test_grapheme_truncate_variation_selector` — string `"✖️" * 12`, verify truncation at 10 clusters (not 10 bytes), no split codepoints.
3. `test_unknown_instruction_no_replacement_char` — parse a line with a bad emoji-prefix; assert `"\ufffd"` not in error message.
4. `test_parse_error_includes_func_name` — parse bad instruction inside named function; assert `"[myFunc]"` in error string.
5. `test_parse_error_no_func_name_at_toplevel` — parse bad instruction before any function directive; assert `"[" not in error str` (no bracket).
6. `test_did_you_mean_variation_selector` — try `✖bad` (bare cross + garbage); check "Did you mean" in error.
7. `test_vmerror_includes_source_line` — run div-by-zero program; catch `VMError`; assert `"➗"` in str(e).
8. `test_vmerror_includes_func_name` — same; assert `"in 🏠"` in str(e).

**Verify**:
```bash
cd /Users/patrickkavanagh/emojiasm && python3 -m pytest tests/test_errors.py -v
```

**Done when**: All 8 new tests pass.

**Commit**: `test(errors): add tests for enriched ParseError and VMError messages`

_Requirements: AC-1.1, AC-1.2, AC-2.1, AC-2.2, AC-3.1, AC-3.2, AC-4.1, AC-4.2_

---

### Task 3.2: Tests for REPL meta commands and error resilience

**Goal**: Cover REPL logic that can be unit-tested without a real TTY.

**Files**: `tests/test_repl.py` (create)

**Do**: Create `/Users/patrickkavanagh/emojiasm/tests/test_repl.py` with:

Test the internal helpers directly (import from `emojiasm.repl`):

1. `test_handle_meta_reset` — create state dict with stack/memory populated; call `_handle_meta(":reset", state)`; assert both are empty.
2. `test_handle_meta_quit_returns_false` — assert `_handle_meta(":quit", state)` returns `False`.
3. `test_handle_meta_exit_returns_false` — same for `:exit`.
4. `test_handle_meta_unknown_returns_true` — `:foo` returns `True` (stays in loop).
5. `test_make_single_instruction_program` — parse `"📥 42"` via `_make_single_instruction_program`; assert program has one instruction with `arg == 42`.
6. `test_repl_input_simulation` — use `unittest.mock.patch("builtins.input", side_effect=["📥 99", ":quit"])` and `io.StringIO` to capture stdout; call `run_repl()`; assert `"stack: [99]"` in output.
7. `test_repl_parse_error_does_not_exit` — patch input with `["❓ bad", ":quit"]`; run_repl; assert no exception raised (REPL continues past error).

**Verify**:
```bash
cd /Users/patrickkavanagh/emojiasm && python3 -m pytest tests/test_repl.py -v
```

**Done when**: All 7 new tests pass.

**Commit**: `test(repl): add unit tests for REPL helpers and error resilience`

_Requirements: AC-5.3, AC-5.4, AC-5.6, AC-5.7, AC-5.9_

---

### Task 3.3: Create static editor files

**Goal**: VS Code extension (3 files) and Vim syntax file.

**Files**:
- `editors/vscode/package.json`
- `editors/vscode/language-configuration.json`
- `editors/vscode/syntaxes/emojiasm.tmLanguage.json`
- `editors/vim/syntax/emojiasm.vim`

**Do**:

Create directory structure:
```
editors/
  vscode/
    package.json
    language-configuration.json
    syntaxes/
      emojiasm.tmLanguage.json
  vim/
    syntax/
      emojiasm.vim
```

`package.json` — minimal VS Code extension manifest:
- `"engines": {"vscode": "^1.74.0"}`
- `"contributes.languages"`: `[{"id": "emojiasm", "extensions": [".emoji"], "configuration": "./language-configuration.json"}]`
- `"contributes.grammars"`: `[{"language": "emojiasm", "scopeName": "source.emojiasm", "path": "./syntaxes/emojiasm.tmLanguage.json"}]`

`language-configuration.json`:
- `"comments": {"lineComment": "💭"}`
- `"brackets"`: empty or minimal

`syntaxes/emojiasm.tmLanguage.json` — TextMate grammar with patterns for each category from design.md. Use `"match"` rules with alternation (`|`) of emoji literals for each group.

`editors/vim/syntax/emojiasm.vim`:
```vim
if exists("b:current_syntax")
  finish
endif
setlocal fileencoding=utf-8

syn match emojiComment "💭.*$"
syn match emojiDirective "^\s*\(📜\|🏷️\|🏷\)"
syn match emojiStack "\(📥\|📤\|📋\|🔀\|🫴\|🔄\)"
syn match emojiArith "\(➕\|➖\|✖️\|✖\|➗\|🔢\|🟰\|📏\|📐\|🤝\|🤙\|🚫\)"
syn match emojiControl "\(👉\|🤔\|😤\|📞\|📲\|🛑\|💤\)"
syn match emojiIO "\(📢\|🖨️\|🖨\|💬\|🎤\|🔟\)"
syn match emojiMem "\(💾\|📂\)"
syn region emojiString start=/"/ end=/"/ skip=/\\"/
syn region emojiString start=/'/ end=/'/ skip=/\\'/
syn region emojiString start=/«/ end=/»/

hi def link emojiComment    Comment
hi def link emojiDirective  Function
hi def link emojiStack      Keyword
hi def link emojiArith      Operator
hi def link emojiControl    Statement
hi def link emojiIO         Special
hi def link emojiMem        Type
hi def link emojiString     String

let b:current_syntax = "emojiasm"
```

Add to `~/.vim/filetype.vim` or instruct in README: `au BufRead,BufNewFile *.emoji set filetype=emojiasm`.

**Verify**:
```bash
python3 -c "import json; json.load(open('/Users/patrickkavanagh/emojiasm/editors/vscode/package.json'))" && echo "package.json valid"
python3 -c "import json; json.load(open('/Users/patrickkavanagh/emojiasm/editors/vscode/syntaxes/emojiasm.tmLanguage.json'))" && echo "grammar valid"
python3 -c "import json; json.load(open('/Users/patrickkavanagh/emojiasm/editors/vscode/language-configuration.json'))" && echo "lang config valid"
```

**Done when**: All three JSON files parse cleanly; vim file exists.

**Commit**: `feat(editors): add VS Code extension and Vim syntax for .emoji files`

_Requirements: FR-7, FR-8, AC-6.1–AC-6.7, AC-7.1–AC-7.2_
_Design: VS Code Extension, Vim Syntax_

---

## Phase 4: Quality Gates

### Task 4.1: Full test suite + coverage check

**Goal**: All tests pass; no regressions.

**Do**:
1. Run full test suite.
2. Check that new tests are counted.
3. Fix any type issues if project uses mypy (`python3 -m mypy emojiasm/ --ignore-missing-imports`).

**Verify**:
```bash
cd /Users/patrickkavanagh/emojiasm && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

**Done when**: 298 original tests + new tests all pass; zero failures.

**Commit**: `fix(dx): address any lint or type issues from DX changes` (only if needed)

---

### Task 4.2: Update README with editor setup section

**Goal**: Document how to use the VS Code extension and Vim syntax file.

**Files**: `README.md`

**Do**: Add a "## Editor Setup" section to `README.md` with:
- VS Code: how to install the local extension (`Extensions > ... > Install from VSIX` or symlink into `~/.vscode/extensions/`).
- Vim: copy `editors/vim/syntax/emojiasm.vim` to `~/.vim/syntax/` and add `au BufRead,BufNewFile *.emoji set filetype=emojiasm` to `~/.vim/filetype.vim`.

**Verify**:
```bash
grep -n "Editor Setup" /Users/patrickkavanagh/emojiasm/README.md
```

**Done when**: Section exists in README.

**Commit**: `docs(readme): add editor setup section for VS Code and Vim`

---

### Task 4.3: Create PR

**Goal**: Open PR for review.

**Do**:
```bash
gh pr create --title "feat: developer experience improvements (error messages, REPL, syntax highlighting)" \
  --body "..."
```

**Verify**: `gh pr checks --watch`

**Done when**: CI is green and PR is open.

---

## Notes

- **POC shortcuts taken**: REPL uses `vm._exec_function` (private method); VM state sharing via direct attribute assignment rather than a clean API.
- **Production TODOs**: Consider exposing a public `VM.step(instruction)` API to replace the private call; consider `readline` tab-completion for opcode emoji in REPL.
- **Backward compat**: `ParseError` and `VMError` signature changes use keyword defaults — all existing `raise ParseError(msg, line_num, line)` call sites are unaffected.
</content>
</invoke>