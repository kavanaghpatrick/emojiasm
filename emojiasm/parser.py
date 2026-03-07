"""Parser for EmojiASM source files."""

import os
import re
import difflib
import unicodedata
from dataclasses import dataclass, field
from .opcodes import EMOJI_TO_OP, DIRECTIVE_FUNC, DIRECTIVE_LABEL, DIRECTIVE_LABEL_ALT, DIRECTIVE_COMMENT, DIRECTIVE_IMPORT, Op, OPS_WITH_ARG


@dataclass
class Instruction:
    op: Op
    arg: object = None
    line_num: int = 0
    source: str = ""


@dataclass
class Function:
    name: str
    instructions: list[Instruction] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)


@dataclass
class Program:
    functions: dict[str, Function] = field(default_factory=dict)
    entry_point: str = "🏠"


class ParseError(Exception):
    def __init__(self, message: str, line_num: int = 0, line: str = "", func_name: str = ""):
        self.line_num = line_num
        self.line = line
        self.func_name = func_name
        loc = f"[{func_name}] " if func_name else ""
        super().__init__(f"💥 Line {line_num}: {loc}{message}\n   → {line}")


def _grapheme_truncate(s: str, n: int = 10) -> str:
    """Return at most n grapheme clusters from s, appending '...' if truncated.

    Cluster detection walks the string codepoint-by-codepoint. A new cluster
    starts at each non-combining character. Variation selectors (U+FE00–U+FE0F),
    characters with a non-zero ``unicodedata.combining()`` value, and characters
    in Unicode category 'Mn' (Non-spacing Mark) are treated as continuation
    bytes of the preceding cluster and do not increment the cluster count.
    Returns ``""`` immediately for an empty input string.
    """
    if not s:
        return ""
    clusters = 0
    end = 0
    i = 0
    while i < len(s):
        ch = s[i]
        # Skip variation selectors (U+FE00–U+FE0F) and combining chars
        if '\ufe00' <= ch <= '\ufe0f' or unicodedata.combining(ch) or unicodedata.category(ch) == 'Mn':
            i += 1
            end = i
            continue
        clusters += 1
        i += 1
        # Consume any following variation selectors or combining chars
        while i < len(s) and ('\ufe00' <= s[i] <= '\ufe0f' or unicodedata.combining(s[i]) or unicodedata.category(s[i]) == 'Mn'):
            i += 1
        end = i
        if clusters >= n:
            break
    if end < len(s):
        return s[:end] + "..."
    return s


def _suggest_opcode(token: str) -> str:
    """Return a 'Did you mean X?' hint if token is close to a known opcode."""
    matches = difflib.get_close_matches(token, list(EMOJI_TO_OP.keys()), n=1, cutoff=0.6)
    return f" Did you mean: {matches[0]}?" if matches else ""


def _extract_string_literal(text: str) -> tuple[str, str]:
    """Extract a quoted string literal, returning (string_value, remaining_text)."""
    text = text.strip()
    if not text or text[0] not in ('"', "'", "«"):
        return None, text

    if text[0] == "«":
        end = text.find("»", 1)
        if end == -1:
            return None, text
        return text[1:end], text[end + 1:]

    quote = text[0]
    escaped = False
    result = []
    for i, ch in enumerate(text[1:], 1):
        if escaped:
            escape_map = {"n": "\n", "t": "\t", "\\": "\\", quote: quote}
            result.append(escape_map.get(ch, ch))
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == quote:
            return "".join(result), text[i + 1:]
        else:
            result.append(ch)
    return None, text


def _parse_arg(text: str, op: Op, line_num: int, line: str):
    """Parse an instruction argument based on the opcode."""
    text = text.strip()
    if not text:
        if op in OPS_WITH_ARG and op != Op.PRINTS:
            raise ParseError(f"Instruction requires an argument", line_num, line)
        return None

    if op == Op.PRINTS:
        val, _ = _extract_string_literal(text)
        if val is not None:
            return val
        return text

    if op in (Op.JMP, Op.JZ, Op.JNZ, Op.CALL):
        return text

    if op in (Op.STORE, Op.LOAD):
        return text

    if op == Op.PUSH:
        if text.startswith(("0x", "0X")):
            return int(text, 16)
        if text.startswith(("0b", "0B")):
            return int(text, 2)
        try:
            return int(text)
        except ValueError:
            pass
        try:
            return float(text)
        except ValueError:
            pass
        val, _ = _extract_string_literal(text)
        if val is not None:
            return val
        return text

    return text


def _resolve_import(name: str, base_path: str, line_num: int, raw_line: str) -> str:
    """Resolve an import name to an absolute file path.

    Searches for ``name.emoji`` in *base_path* first, then each directory
    listed in the ``EMOJIASM_PATH`` environment variable (colon-separated).
    Returns the absolute path of the first match, or raises ``ParseError``.
    """
    filename = f"{name}.emoji"

    # 1. Check relative to importing file's directory (or cwd)
    if base_path:
        candidate = os.path.join(base_path, filename)
    else:
        candidate = os.path.join(os.getcwd(), filename)
    if os.path.isfile(candidate):
        return os.path.abspath(candidate)

    # 2. Check EMOJIASM_PATH
    env_path = os.environ.get("EMOJIASM_PATH", "")
    if env_path:
        for directory in env_path.split(os.pathsep):
            directory = directory.strip()
            if not directory:
                continue
            candidate = os.path.join(directory, filename)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

    raise ParseError(
        f"Cannot find module '{name}' ({filename})",
        line_num,
        raw_line,
    )


def parse(source: str, base_path: str = "", _seen_files: set | None = None) -> Program:
    """Parse EmojiASM source code into a Program.

    Parameters
    ----------
    source : str
        The EmojiASM source text.
    base_path : str
        Directory used to resolve ``📦 name`` import directives.  When empty,
        the current working directory is used as fallback.
    _seen_files : set or None
        Internal — tracks already-visited file paths to detect circular
        imports.  Callers should not pass this.
    """
    program = Program()
    current_func = None
    lines = source.split("\n")

    if _seen_files is None:
        _seen_files = set()

    for line_num, raw_line in enumerate(lines, 1):
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith(DIRECTIVE_COMMENT):
            continue

        # --- import directive ---
        if line.startswith(DIRECTIVE_IMPORT):
            name = line[len(DIRECTIVE_IMPORT):].strip()
            if not name:
                raise ParseError("Import requires a module name", line_num, raw_line)

            resolved = _resolve_import(name, base_path, line_num, raw_line)

            if resolved in _seen_files:
                raise ParseError(
                    f"Circular import detected: {name} ({resolved})",
                    line_num,
                    raw_line,
                )

            try:
                with open(resolved, "r", encoding="utf-8") as f:
                    imported_source = f.read()
            except OSError as exc:
                raise ParseError(
                    f"Cannot read module '{name}': {exc}",
                    line_num,
                    raw_line,
                )

            imported_base = os.path.dirname(resolved)
            # Pass a copy with the resolved file added so that sibling
            # imports (diamond pattern) don't falsely trigger circular
            # detection, while ancestor chains still do.
            child_seen = _seen_files | {resolved}
            imported_program = parse(imported_source, base_path=imported_base, _seen_files=child_seen)

            # Merge imported functions into current program (last-wins on conflict)
            for fname, func in imported_program.functions.items():
                program.functions[fname] = func

            continue

        if line.startswith(DIRECTIVE_FUNC):
            name = line[len(DIRECTIVE_FUNC):].strip()
            if not name:
                name = "🏠"
            current_func = Function(name=name)
            program.functions[name] = current_func
            continue

        if line.startswith(DIRECTIVE_LABEL) or line.startswith(DIRECTIVE_LABEL_ALT):
            if current_func is None:
                raise ParseError("Label outside of function", line_num, raw_line)
            directive = DIRECTIVE_LABEL if line.startswith(DIRECTIVE_LABEL) else DIRECTIVE_LABEL_ALT
            label_name = line[len(directive):].strip()
            if not label_name:
                raise ParseError("Label requires a name", line_num, raw_line)
            current_func.labels[label_name] = len(current_func.instructions)
            continue

        emoji = None
        rest = ""
        for emoji_candidate, op in EMOJI_TO_OP.items():
            if line.startswith(emoji_candidate):
                emoji = emoji_candidate
                rest = line[len(emoji_candidate):]
                break

        if emoji is None:
            preview = _grapheme_truncate(line, 10)
            first_token = line.split()[0] if line.split() else line
            hint = _suggest_opcode(first_token)
            raise ParseError(
                f"Unknown instruction: {preview}{hint}",
                line_num,
                raw_line,
                func_name=current_func.name if current_func else "",
            )

        if current_func is None:
            current_func = Function(name="🏠")
            program.functions["🏠"] = current_func

        op = EMOJI_TO_OP[emoji]
        arg = _parse_arg(rest, op, line_num, raw_line)

        current_func.instructions.append(Instruction(
            op=op, arg=arg, line_num=line_num, source=raw_line.strip()
        ))

    if not program.functions:
        raise ParseError("No instructions found", 0, "")

    if "🏠" not in program.functions:
        first = next(iter(program.functions))
        program.entry_point = first

    return program
