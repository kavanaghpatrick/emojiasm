"""GPU bytecode compiler: EmojiASM Program -> packed uint32[] bytecode.

Encodes a parsed Program into a compact binary format suitable for GPU
execution via Metal/MSL switch-case dispatch (KB #102). The three-stage
pipeline (KB #131) is: Analyze -> Encode -> Emit.

Instruction format (uint32):
    [31:24]  opcode   (8 bits)  -- up to 256 opcodes
    [23:0]   operand  (24 bits) -- constant pool index, jump target, or mem cell ID

Float literals live in a separate constant pool; PUSH encodes the pool
index in the operand field, not the value itself.

GPU tier classification (extends _uses_strings(), KB #106):
    Tier 1: Numeric-only (fast GPU path)
    Tier 2: Numeric + output (PRINT/PRINTLN but no INPUT; GPU with output buffer)
    Tier 3: Full features (INPUT/strings require CPU fallback)

Max stack depth capped at 128 entries in device memory (KB #147).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from .opcodes import Op
from .parser import Program, Function, Instruction


# ── Opcode map: Op enum -> uint8 GPU opcode ──────────────────────────────

OP_MAP: dict[Op, int] = {
    # Stack
    Op.PUSH:    0x01,
    Op.POP:     0x02,
    Op.DUP:     0x03,
    Op.SWAP:    0x04,
    Op.OVER:    0x05,
    Op.ROT:     0x06,
    # Arithmetic
    Op.ADD:     0x10,
    Op.SUB:     0x11,
    Op.MUL:     0x12,
    Op.DIV:     0x13,
    Op.MOD:     0x14,
    # Comparison & Logic
    Op.CMP_EQ:  0x20,
    Op.CMP_LT:  0x21,
    Op.CMP_GT:  0x22,
    Op.AND:     0x23,
    Op.OR:      0x24,
    Op.NOT:     0x25,
    # Control Flow
    Op.JMP:     0x30,
    Op.JZ:      0x31,
    Op.JNZ:     0x32,
    Op.CALL:    0x33,
    Op.RET:     0x34,
    Op.HALT:    0x35,
    Op.NOP:     0x36,
    # Memory
    Op.STORE:   0x40,
    Op.LOAD:    0x41,
    # I/O (GPU-supported subset)
    Op.PRINT:   0x50,
    Op.PRINTLN: 0x51,
    # Random
    Op.RANDOM:  0x60,
}

# Reverse map for disassembly / debugging
OPCODE_TO_OP: dict[int, Op] = {v: k for k, v in OP_MAP.items()}

# Maximum operand value (24-bit unsigned)
_MAX_OPERAND = (1 << 24) - 1

# Maximum stack depth allowed on GPU (KB #147)
_GPU_MAX_STACK = 128


# ── Output dataclass ─────────────────────────────────────────────────────

@dataclass
class GpuProgram:
    """Encoded program ready for GPU execution."""
    bytecode: list[int]       # packed uint32 instructions
    constants: list[float]    # float literal pool
    num_functions: int        # count of flattened functions
    entry_offset: int         # bytecode offset of entry function
    max_stack_depth: int      # static analysis result
    gpu_tier: int             # 1=numeric, 2=output, 3=cpu-only


# ── GPU tier classification ──────────────────────────────────────────────

# Ops that require string support
_STRING_OPS = frozenset({
    Op.PRINTS, Op.STRLEN, Op.SUBSTR, Op.STRINDEX, Op.STR2NUM, Op.NUM2STR,
})

# Ops that require interactive input (CPU-only)
_INPUT_OPS = frozenset({Op.INPUT, Op.INPUT_NUM})

# Ops that produce output (tier 2 indicator when no strings/input)
_OUTPUT_OPS = frozenset({Op.PRINT, Op.PRINTLN})


def _uses_strings(program: Program) -> bool:
    """Check if any function uses string operations."""
    for func in program.functions.values():
        for inst in func.instructions:
            if inst.op in _STRING_OPS:
                return True
            # PUSH with a string argument also counts
            if inst.op == Op.PUSH and isinstance(inst.arg, str):
                return True
    return False


def gpu_tier(program: Program) -> int:
    """Classify program for GPU execution capability.

    Tier 1: Numeric-only (fast GPU path) -- no I/O at all
    Tier 2: Numeric + output -- PRINT/PRINTLN but no INPUT (GPU with output buffer)
    Tier 3: Full features -- INPUT/strings require CPU fallback
    """
    has_input = False
    has_output = False

    for func in program.functions.values():
        for inst in func.instructions:
            if inst.op in _INPUT_OPS:
                has_input = True
            if inst.op in _OUTPUT_OPS:
                has_output = True

    if has_input or _uses_strings(program):
        return 3
    if has_output:
        return 2
    return 1


# ── Internal compilation helpers ─────────────────────────────────────────

def _flatten_functions(
    program: Program,
) -> tuple[list[Instruction], dict[str, int], dict[str, dict[str, int]]]:
    """Flatten all functions into a linear instruction list.

    Entry function is placed first. Returns:
        - Linear instruction list
        - Function name -> bytecode offset mapping
        - Function name -> {label_name -> absolute bytecode offset}
    """
    instructions: list[Instruction] = []
    func_offsets: dict[str, int] = {}
    label_offsets: dict[str, dict[str, int]] = {}

    # Entry function first
    entry_name = program.entry_point
    entry_func = program.functions[entry_name]
    func_offsets[entry_name] = 0
    label_offsets[entry_name] = {
        lbl: ip for lbl, ip in entry_func.labels.items()
    }
    instructions.extend(entry_func.instructions)

    # Remaining functions in stable order
    for name, func in program.functions.items():
        if name == entry_name:
            continue
        offset = len(instructions)
        func_offsets[name] = offset
        label_offsets[name] = {
            lbl: offset + ip for lbl, ip in func.labels.items()
        }
        instructions.extend(func.instructions)

    return instructions, func_offsets, label_offsets


def _build_constant_pool(instructions: list[Instruction]) -> tuple[dict[float, int], list[float]]:
    """Build a deduplicated float constant pool from PUSH instructions.

    Returns:
        - value -> pool index mapping
        - ordered list of unique constants
    """
    pool_map: dict[float, int] = {}
    pool: list[float] = []

    for inst in instructions:
        if inst.op == Op.PUSH and isinstance(inst.arg, (int, float)):
            val = float(inst.arg)
            if val not in pool_map:
                pool_map[val] = len(pool)
                pool.append(val)

    return pool_map, pool


def _build_memory_map(program: Program) -> dict[str, int]:
    """Map emoji memory cell names to integer indices 0..N-1.

    Cells are sorted for deterministic ordering across compilations.
    """
    cells: set[str] = set()
    for func in program.functions.values():
        for inst in func.instructions:
            if inst.op in (Op.STORE, Op.LOAD):
                cells.add(inst.arg)
    return {name: idx for idx, name in enumerate(sorted(cells))}


# Stack depth effects for each opcode:
#   positive = pushes, negative = pops, net = change
_STACK_EFFECTS: dict[Op, int] = {
    Op.PUSH:    +1,
    Op.POP:     -1,
    Op.DUP:     +1,    # peeks 1, pushes 1 => net +1
    Op.SWAP:     0,    # pops 2, pushes 2
    Op.OVER:    +1,    # peeks, pushes 1
    Op.ROT:      0,    # pops 3, pushes 3
    Op.ADD:     -1,    # pops 2, pushes 1
    Op.SUB:     -1,
    Op.MUL:     -1,
    Op.DIV:     -1,
    Op.MOD:     -1,
    Op.CMP_EQ:  -1,
    Op.CMP_LT:  -1,
    Op.CMP_GT:  -1,
    Op.AND:     -1,
    Op.OR:      -1,
    Op.NOT:      0,    # pops 1, pushes 1
    Op.JMP:      0,
    Op.JZ:      -1,    # pops condition
    Op.JNZ:     -1,    # pops condition
    Op.CALL:     0,    # no stack effect (callee manages its own)
    Op.RET:      0,
    Op.HALT:     0,
    Op.NOP:      0,
    Op.STORE:   -1,    # pops value
    Op.LOAD:    +1,    # pushes value
    Op.PRINT:   -1,    # pops value
    Op.PRINTLN: -1,    # pops value
    Op.RANDOM:  +1,    # pushes random float
}


def _analyze_max_stack_depth(program: Program) -> int:
    """Conservative max stack depth via instruction walk.

    Walks each function linearly (ignoring branches — conservative because
    we take the max across all instruction positions). Caps at 128 per
    KB #147 GPU memory budget.
    """
    max_depth = 0

    for func in program.functions.values():
        depth = 0
        local_max = 0
        for inst in func.instructions:
            effect = _STACK_EFFECTS.get(inst.op, 0)
            depth += effect
            if depth < 0:
                depth = 0  # conservative: assume stack was already populated
            if depth > local_max:
                local_max = depth
        if local_max > max_depth:
            max_depth = local_max

    return min(max_depth, _GPU_MAX_STACK)


def _pack(opcode: int, operand: int = 0) -> int:
    """Pack an opcode and operand into a uint32.

    Layout: [31:24] opcode (8 bits), [23:0] operand (24 bits).
    """
    if operand < 0 or operand > _MAX_OPERAND:
        raise ValueError(
            f"Operand {operand} out of range [0, {_MAX_OPERAND}]"
        )
    return (opcode << 24) | (operand & 0xFFFFFF)


def _unpack(word: int) -> tuple[int, int]:
    """Unpack a uint32 into (opcode, operand)."""
    return (word >> 24) & 0xFF, word & 0xFFFFFF


# ── Main entry point ─────────────────────────────────────────────────────

class BytecodeError(Exception):
    """Raised when a program cannot be compiled to GPU bytecode."""


def compile_to_bytecode(program: Program) -> GpuProgram:
    """Compile a parsed Program to GPU bytecode format.

    Steps (three-stage pipeline per KB #131):
    1. Analyze: classify gpu_tier, flatten functions, build pools
    2. Encode: translate each instruction to packed uint32
    3. Emit: assemble GpuProgram with all metadata

    The traversal pattern mirrors the C compiler (KB #123) but emits
    packed bytecode instead of C source.
    """
    tier = gpu_tier(program)

    # Stage 1: Analyze
    flat_instructions, func_offsets, label_offsets = _flatten_functions(program)
    const_map, const_pool = _build_constant_pool(flat_instructions)
    mem_map = _build_memory_map(program)
    max_depth = _analyze_max_stack_depth(program)

    # We need to know which function each instruction belongs to for label resolution.
    # Build an instruction-index -> function-name mapping.
    inst_func_map: list[str] = []
    entry_name = program.entry_point
    entry_func = program.functions[entry_name]
    inst_func_map.extend([entry_name] * len(entry_func.instructions))
    for name, func in program.functions.items():
        if name == entry_name:
            continue
        inst_func_map.extend([name] * len(func.instructions))

    # Stage 2: Encode
    bytecode: list[int] = []

    for idx, inst in enumerate(flat_instructions):
        op = inst.op

        # Check if this opcode is supported for GPU
        if op not in OP_MAP:
            raise BytecodeError(
                f"Opcode {op.name} is not supported in GPU bytecode"
            )

        opcode = OP_MAP[op]

        if op == Op.PUSH:
            if isinstance(inst.arg, (int, float)):
                operand = const_map[float(inst.arg)]
            else:
                raise BytecodeError(
                    f"PUSH with non-numeric argument '{inst.arg}' "
                    f"cannot be compiled to GPU bytecode"
                )
            bytecode.append(_pack(opcode, operand))

        elif op in (Op.JMP, Op.JZ, Op.JNZ):
            # Resolve label to absolute bytecode offset
            func_name = inst_func_map[idx]
            labels = label_offsets[func_name]
            if inst.arg not in labels:
                raise BytecodeError(
                    f"Unresolved label '{inst.arg}' in function '{func_name}'"
                )
            target = labels[inst.arg]
            bytecode.append(_pack(opcode, target))

        elif op == Op.CALL:
            # Resolve function name to bytecode offset
            if inst.arg not in func_offsets:
                raise BytecodeError(
                    f"Unresolved function '{inst.arg}'"
                )
            target = func_offsets[inst.arg]
            bytecode.append(_pack(opcode, target))

        elif op in (Op.STORE, Op.LOAD):
            if inst.arg not in mem_map:
                raise BytecodeError(
                    f"Unresolved memory cell '{inst.arg}'"
                )
            cell_idx = mem_map[inst.arg]
            bytecode.append(_pack(opcode, cell_idx))

        else:
            # Ops with no operand
            bytecode.append(_pack(opcode, 0))

    # Stage 3: Emit
    return GpuProgram(
        bytecode=bytecode,
        constants=const_pool,
        num_functions=len(program.functions),
        entry_offset=func_offsets[program.entry_point],
        max_stack_depth=max_depth,
        gpu_tier=tier,
    )
