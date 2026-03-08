"""EmojiASM - An assembly language written entirely in emojis."""

__version__ = "1.0.0"

from .inference import EmojiASMTool
from .transpiler import transpile, transpile_to_source, TranspileError

__all__ = ["EmojiASMTool", "transpile", "transpile_to_source", "TranspileError"]
