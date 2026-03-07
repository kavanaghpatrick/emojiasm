"""Disassembler for EmojiASM programs."""

from .opcodes import OP_TO_EMOJI, OPS_WITH_ARG
from .parser import Program


def disassemble(program: Program) -> str:
    lines = []
    for func_name, func in program.functions.items():
        lines.append(f"📜 {func_name}")
        label_positions = {v: k for k, v in func.labels.items()}
        for i, inst in enumerate(func.instructions):
            if i in label_positions:
                lines.append(f"  🏷️ {label_positions[i]}")
            emoji = OP_TO_EMOJI.get(inst.op, "❓")
            if inst.op in OPS_WITH_ARG and inst.arg is not None:
                if isinstance(inst.arg, str) and inst.op.name == "PRINTS":
                    lines.append(f"  {emoji} \"{inst.arg}\"")
                else:
                    lines.append(f"  {emoji} {inst.arg}")
            else:
                lines.append(f"  {emoji}")
        lines.append("")
    return "\n".join(lines)
