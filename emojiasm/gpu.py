"""GPU interface module for EmojiASM Metal kernel.

Provides the MSL kernel source and opcode validation utilities.
The actual Metal pipeline setup is deferred to a future runtime module;
this module handles kernel source loading and opcode consistency checks.
"""

from __future__ import annotations

from pathlib import Path

from .bytecode import OP_MAP
from .opcodes import Op


# ── Constants ────────────────────────────────────────────────────────────

DEFAULT_STACK_DEPTH = 128
DEFAULT_MAX_STEPS = 1_000_000
DEFAULT_THREADGROUP_SIZE = 256

# Path to the Metal shader source
_METAL_DIR = Path(__file__).parent / "metal"
_KERNEL_PATH = _METAL_DIR / "vm.metal"


# ── GPU opcode map (mirrors bytecode.py OP_MAP) ─────────────────────────

GPU_OPCODES: dict[str, int] = {
    # Stack
    "PUSH":    0x01,
    "POP":     0x02,
    "DUP":     0x03,
    "SWAP":    0x04,
    "OVER":    0x05,
    "ROT":     0x06,
    # Arithmetic
    "ADD":     0x10,
    "SUB":     0x11,
    "MUL":     0x12,
    "DIV":     0x13,
    "MOD":     0x14,
    # Comparison & Logic
    "EQ":      0x20,
    "LT":      0x21,
    "GT":      0x22,
    "AND":     0x23,
    "OR":      0x24,
    "NOT":     0x25,
    # Control Flow
    "JMP":     0x30,
    "JZ":      0x31,
    "JNZ":     0x32,
    "CALL":    0x33,
    "RET":     0x34,
    "HALT":    0x35,
    "NOP":     0x36,
    # Memory
    "STORE":   0x40,
    "LOAD":    0x41,
    # I/O
    "PRINT":   0x50,
    "PRINTLN": 0x51,
    # Random
    "RANDOM":  0x60,
}

# Mapping from GPU_OPCODES key names to bytecode.py Op enum names.
# Most are the same, but comparison ops have a CMP_ prefix in the Op enum.
_GPU_NAME_TO_OP_NAME: dict[str, str] = {
    "EQ": "CMP_EQ",
    "LT": "CMP_LT",
    "GT": "CMP_GT",
}


# ── Public API ───────────────────────────────────────────────────────────

def get_kernel_source() -> str:
    """Read and return the MSL kernel source as a string.

    Raises FileNotFoundError if the .metal file is missing.
    """
    return _KERNEL_PATH.read_text(encoding="utf-8")


def validate_opcodes() -> None:
    """Validate that GPU_OPCODES matches bytecode.py OP_MAP exactly.

    Raises ValueError with a descriptive message if any mismatch is found.
    """
    errors: list[str] = []

    # Check every GPU opcode has a matching OP_MAP entry
    for gpu_name, gpu_code in GPU_OPCODES.items():
        op_name = _GPU_NAME_TO_OP_NAME.get(gpu_name, gpu_name)
        try:
            op = Op[op_name]
        except KeyError:
            errors.append(f"GPU opcode {gpu_name!r} has no matching Op.{op_name}")
            continue

        if op not in OP_MAP:
            errors.append(
                f"Op.{op_name} (GPU: {gpu_name!r}) is not in bytecode.py OP_MAP"
            )
            continue

        if OP_MAP[op] != gpu_code:
            errors.append(
                f"Mismatch for {gpu_name!r}: GPU=0x{gpu_code:02X}, "
                f"OP_MAP[Op.{op_name}]=0x{OP_MAP[op]:02X}"
            )

    # Check every OP_MAP entry has a matching GPU opcode
    for op, code in OP_MAP.items():
        # Find the GPU name for this Op
        op_name = op.name
        gpu_name = None
        for gn, on in _GPU_NAME_TO_OP_NAME.items():
            if on == op_name:
                gpu_name = gn
                break
        if gpu_name is None:
            gpu_name = op_name

        if gpu_name not in GPU_OPCODES:
            errors.append(
                f"OP_MAP has Op.{op_name} (0x{code:02X}) but GPU_OPCODES "
                f"has no {gpu_name!r} entry"
            )

    if errors:
        raise ValueError(
            "GPU opcode validation failed:\n  " + "\n  ".join(errors)
        )
