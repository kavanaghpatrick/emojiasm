"""Emoji opcode definitions for EmojiASM."""

from enum import IntEnum, auto


class Op(IntEnum):
    PUSH = auto()
    POP = auto()
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    PRINT = auto()
    PRINTLN = auto()
    PRINTS = auto()
    DUP = auto()
    SWAP = auto()
    OVER = auto()
    ROT = auto()
    JMP = auto()
    JZ = auto()
    JNZ = auto()
    CMP_EQ = auto()
    CMP_LT = auto()
    CMP_GT = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    STORE = auto()
    LOAD = auto()
    CALL = auto()
    RET = auto()
    INPUT = auto()
    INPUT_NUM = auto()
    HALT = auto()
    NOP = auto()


# Emoji -> Opcode mapping
EMOJI_TO_OP = {
    "📥": Op.PUSH,
    "📤": Op.POP,
    "➕": Op.ADD,
    "➖": Op.SUB,
    "✖️": Op.MUL,
    "✖": Op.MUL,
    "➗": Op.DIV,
    "🔢": Op.MOD,
    "📢": Op.PRINT,
    "🖨️": Op.PRINTLN,
    "🖨": Op.PRINTLN,
    "💬": Op.PRINTS,
    "📋": Op.DUP,
    "🔀": Op.SWAP,
    "🫴": Op.OVER,
    "🔄": Op.ROT,
    "👉": Op.JMP,
    "🤔": Op.JZ,
    "😤": Op.JNZ,
    "🟰": Op.CMP_EQ,
    "📏": Op.CMP_LT,
    "📐": Op.CMP_GT,
    "🤝": Op.AND,
    "🤙": Op.OR,
    "🚫": Op.NOT,
    "💾": Op.STORE,
    "📂": Op.LOAD,
    "📞": Op.CALL,
    "📲": Op.RET,
    "🎤": Op.INPUT,
    "🔟": Op.INPUT_NUM,
    "🛑": Op.HALT,
    "💤": Op.NOP,
}

# Reverse mapping for disassembly
OP_TO_EMOJI = {v: k for k, v in EMOJI_TO_OP.items()}

# Directives (not opcodes, but structural)
DIRECTIVE_FUNC = "📜"
DIRECTIVE_LABEL = "🏷️"
DIRECTIVE_LABEL_ALT = "🏷"
DIRECTIVE_COMMENT = "💭"
DIRECTIVE_DATA = "📊"

# Ops that take an argument
OPS_WITH_ARG = {
    Op.PUSH, Op.JMP, Op.JZ, Op.JNZ,
    Op.CALL, Op.STORE, Op.LOAD, Op.PRINTS,
}
