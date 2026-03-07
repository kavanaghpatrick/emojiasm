"""Parser for EmojiASM source files."""

import re
import difflib
import unicodedata
from dataclasses import dataclass, field
from .opcodes import EMOJI_TO_OP, DIRECTIVE_FUNC, DIRECTIVE_LABEL, DIRECTIVE_LABEL_ALT, DIRECTIVE_COMMENT, Op, OPS_WITH_ARG


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
    """Return at most n grapheme clusters from s, appending '...' if truncated."""
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


def parse(source: str) -> Program:
    """Parse EmojiASM source code into a Program."""
    program = Program()
    current_func = None
    lines = source.split("\n")

    for line_num, raw_line in enumerate(lines, 1):
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith(DIRECTIVE_COMMENT):
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
