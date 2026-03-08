"""GPU interface module for EmojiASM Metal kernel.

Provides the MSL kernel source, opcode validation utilities, and the
MLX-based GPU runtime that dispatches EmojiASM programs as Metal compute
kernels via ``mx.fast.metal_kernel()``.
"""

from __future__ import annotations

import math
import re
import time
from functools import lru_cache
from pathlib import Path

from .bytecode import OP_MAP, compile_to_bytecode, gpu_tier, GpuProgram, _build_string_table
from .opcodes import Op
from .parser import Program


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
    # Math
    "POW":     0x15,
    "SQRT":    0x16,
    "SIN":     0x17,
    "COS":     0x18,
    "EXP":     0x19,
    "LOG":     0x1A,
    "ABS":     0x1B,
    "MIN":     0x1C,
    "MAX":     0x1D,
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


# ── GPU availability ────────────────────────────────────────────────────

def gpu_available() -> bool:
    """Check if MLX and Metal GPU are available.

    Returns False (never raises) if MLX is not installed or no Metal
    GPU device is present.
    """
    try:
        import mlx.core as mx
        # Check that a GPU device exists
        mx.default_device()
        return True
    except Exception:
        return False


# ── MLX kernel creation ─────────────────────────────────────────────────

def _split_kernel_source() -> tuple[str, str]:
    """Split vm.metal into header and body for MLX metal_kernel.

    MLX's ``mx.fast.metal_kernel()`` auto-generates the kernel function
    signature.  The ``header`` receives everything *before* the kernel
    function body (constants, helper structs, PRNG functions) and the
    ``source`` receives the function body (the code between the outermost
    braces of ``kernel void emojiasm_vm(...) { ... }``).

    The original kernel uses ``constant uint32_t&`` reference parameters
    for scalars, but MLX generates ``const constant uint32_t*`` pointers.
    The body is patched so ``num_insts``, ``stack_depth``, and ``max_steps``
    are accessed via ``[0]`` indexing instead of by-reference.
    """
    raw = get_kernel_source()

    # Find the kernel function definition start
    match = re.search(
        r"kernel\s+void\s+emojiasm_vm\s*\(",
        raw,
        re.DOTALL,
    )
    if match is None:
        raise RuntimeError("Cannot locate emojiasm_vm kernel in vm.metal")

    header_end = match.start()

    # The parameter list contains nested parens (e.g. [[buffer(0)]]),
    # so we manually find the matching closing paren.
    paren_start = match.end()
    depth = 1
    pos = paren_start
    while depth > 0 and pos < len(raw):
        if raw[pos] == "(":
            depth += 1
        elif raw[pos] == ")":
            depth -= 1
        pos += 1
    # pos is right after closing paren.  Find the opening brace.
    body_start = raw.index("{", pos) + 1

    # Find the matching closing brace for the kernel function
    depth = 1
    pos = body_start
    while depth > 0 and pos < len(raw):
        if raw[pos] == "{":
            depth += 1
        elif raw[pos] == "}":
            depth -= 1
        pos += 1
    body_end = pos - 1  # position of the closing "}"

    # Ensure header ends with a newline: MLX concatenates the header
    # directly with the generated kernel signature, so a missing newline
    # would merge the last header line with ``[[kernel]] void ...``.
    header = raw[:header_end].strip() + "\n"
    body = raw[body_start:body_end].strip()

    # MLX generates pointer parameters, not references.  The original
    # kernel accesses num_insts, stack_depth, max_steps as bare names
    # (references).  We need to replace them with pointer dereferences.
    # Use word-boundary replacements to avoid hitting substrings.
    # Also, the tid comes from uint3 thread_position_in_grid in MLX.
    body = (
        "    uint tid = thread_position_in_grid.x;\n"
        "    // Cast MLX-generated uint32 pointers to proper types for output buffer\n"
        "    device OutputEntry* output_buf = (device OutputEntry*)output_buf_raw;\n"
        "    device uint32_t* output_counts = output_counts_raw;\n"
    ) + body

    # Replace scalar reference accesses with pointer dereferences.
    # We need to be careful not to replace occurrences inside strings or
    # in contexts where they are already indexed.  The kernel uses these
    # as plain identifiers (e.g. ``if (sp >= int(stack_depth))``).
    for scalar in ("num_insts", "stack_depth", "max_steps", "output_cap"):
        # Replace occurrences that are NOT already followed by '['
        body = re.sub(
            rf"\b{scalar}\b(?!\s*\[)",
            f"{scalar}[0]",
            body,
        )

    return header, body


@lru_cache(maxsize=1)
def _get_kernel():
    """Create and cache the MLX Metal kernel for EmojiASM VM dispatch.

    Returns the callable kernel object produced by ``mx.fast.metal_kernel()``.
    Raises ImportError if MLX is not available.

    The kernel always accepts output buffer parameters (buffers 8-10).
    For Tier 1 programs, output_cap is set to 0, disabling output capture.
    """
    import mlx.core as mx

    header, source = _split_kernel_source()

    kernel = mx.fast.metal_kernel(
        name="emojiasm_vm",
        input_names=[
            "bytecode", "constants",
            "num_insts", "stack_depth", "max_steps",
            "output_cap",
        ],
        output_names=["stacks", "results", "status", "output_buf_raw", "output_counts_raw"],
        source=source,
        header=header,
    )
    return kernel


# ── Statistics helper ───────────────────────────────────────────────────

def _stats(values: list[float]) -> dict:
    """Compute summary statistics from a list of float values.

    Returns dict with mean, std, min, max, count.  Returns zeros when
    *values* is empty.
    """
    if not values:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "count": 0}

    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    return {
        "mean": mean,
        "std": math.sqrt(variance),
        "min": min(values),
        "max": max(values),
        "count": n,
    }


# ── Output reconstruction ────────────────────────────────────────────────

# Number of uint32 fields per OutputEntry struct (thread_id, seq_num, type, value-as-uint32, str_idx)
_OUTPUT_ENTRY_FIELDS = 5


def _format_float(v: float) -> str:
    """Format a float value for output, using integer format when appropriate."""
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return str(v)


def _reconstruct_output(
    output_data: list[int],
    string_table: list[str],
    n_threads: int,
) -> dict[int, str]:
    """Reconstruct per-thread output strings from the raw output buffer.

    Args:
        output_data: Flat list of uint32 values from the output buffer,
            grouped as (thread_id, seq_num, type, value_bits, str_idx) per entry.
        string_table: List of string literals for type=1 entries.
        n_threads: Number of threads (for validation).

    Returns:
        dict mapping thread_id to the reconstructed output string.
    """
    import struct

    if not output_data:
        return {}

    # Parse entries from flat uint32 array
    entries: list[tuple[int, int, int, float, int]] = []
    n_entries = len(output_data) // _OUTPUT_ENTRY_FIELDS
    for i in range(n_entries):
        base = i * _OUTPUT_ENTRY_FIELDS
        thread_id = output_data[base]
        seq_num = output_data[base + 1]
        entry_type = output_data[base + 2]
        # value is stored as float but represented in uint32 buffer;
        # reinterpret the bits
        value_bits = output_data[base + 3]
        value = struct.unpack('f', struct.pack('I', value_bits))[0]
        str_idx = output_data[base + 4]

        # Skip empty/padding entries (thread_id=0, seq_num=0, type=0, value=0)
        # when they appear beyond the actual written entries
        entries.append((thread_id, seq_num, entry_type, value, str_idx))

    # Sort by (thread_id, seq_num) for correct per-thread ordering
    entries.sort(key=lambda e: (e[0], e[1]))

    # Build per-thread output strings
    outputs: dict[int, str] = {}
    for thread_id, seq_num, entry_type, value, str_idx in entries:
        if thread_id not in outputs:
            outputs[thread_id] = ""

        if entry_type == 0:
            # Float value
            outputs[thread_id] += _format_float(value)
        elif entry_type == 1:
            # String from table
            if str_idx < len(string_table):
                outputs[thread_id] += string_table[str_idx]
        elif entry_type == 2:
            # Newline marker
            outputs[thread_id] += "\n"

    return outputs


# ── Main GPU execution ──────────────────────────────────────────────────

# Status code mapping (mirrors vm.metal STATUS_* constants)
_STATUS_NAMES = {0: "ok", 1: "error", 2: "div_by_zero", 3: "timeout"}


def gpu_run(
    program: Program,
    n: int = 1000,
    max_steps: int = DEFAULT_MAX_STEPS,
    stack_depth: int = DEFAULT_STACK_DEPTH,
) -> dict:
    """Execute an EmojiASM program on the GPU via MLX Metal kernel.

    Each of the *n* GPU threads runs an independent VM instance
    interpreting the same bytecode.  Programs with RANDOM will produce
    different results per thread (Philox PRNG seeded by thread ID).

    Args:
        program: Parsed EmojiASM Program.
        n: Number of parallel GPU instances.
        max_steps: Per-instance step limit before timeout.
        stack_depth: Per-instance stack size.

    Returns:
        dict with keys: success, mode, instances, completed, failed,
        results, stats, total_time_ms.

    Raises:
        RuntimeError: If the program uses INPUT (tier 3) or MLX is
            unavailable.
    """
    tier = gpu_tier(program)
    if tier == 3:
        raise RuntimeError(
            "Program uses INPUT and cannot run on GPU (tier 3). "
            "Use CPU execution instead."
        )

    import mlx.core as mx

    t0 = time.perf_counter()

    # Compile to bytecode
    gpu_prog: GpuProgram = compile_to_bytecode(program)

    # Create MLX arrays
    bc_array = mx.array(gpu_prog.bytecode, dtype=mx.uint32)
    # Constant pool must have at least one element
    const_pool = gpu_prog.constants if gpu_prog.constants else [0.0]
    const_array = mx.array(const_pool, dtype=mx.float32)
    num_insts_array = mx.array([len(gpu_prog.bytecode)], dtype=mx.uint32)
    stack_depth_array = mx.array([stack_depth], dtype=mx.uint32)
    max_steps_array = mx.array([max_steps], dtype=mx.uint32)

    # Output buffer sizing for Tier 2
    # Each PRINT/PRINTLN generates 1-2 entries per thread.
    # Conservative estimate: allow up to 64 output entries per thread.
    is_tier2 = tier == 2
    if is_tier2:
        max_out_per_thread = 64  # max output entries per thread
    else:
        max_out_per_thread = 0

    output_cap_array = mx.array([max_out_per_thread], dtype=mx.uint32)

    # Get (cached) kernel
    kernel = _get_kernel()

    # Dispatch
    tg_size = min(n, DEFAULT_THREADGROUP_SIZE)

    # Output buffer: each OutputEntry is 5 uint32s (per-thread slots)
    # Total buffer size: n_threads * max_out_per_thread * fields_per_entry
    total_output_entries = n * max_out_per_thread if max_out_per_thread > 0 else 0
    output_buf_size = max(total_output_entries * _OUTPUT_ENTRY_FIELDS, 1)

    outputs = kernel(
        inputs=[
            bc_array, const_array,
            num_insts_array, stack_depth_array, max_steps_array,
            output_cap_array,
        ],
        grid=(n, 1, 1),
        threadgroup=(tg_size, 1, 1),
        output_shapes=[
            (n * stack_depth,),     # stacks
            (n,),                   # results
            (n,),                   # status
            (output_buf_size,),     # output_buf (as flat uint32)
            (max(n, 1),),           # output_counts (per-thread entry counts)
        ],
        output_dtypes=[
            mx.float32,   # stacks
            mx.float32,   # results
            mx.uint32,    # status
            mx.uint32,    # output_buf
            mx.uint32,    # output_counts
        ],
    )

    # Force GPU execution
    mx.eval(*outputs)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Parse results
    stacks_out, results_out, status_out, output_buf_out, output_counts_out = outputs
    results_list = results_out.tolist()
    status_list = status_out.tolist()

    completed = sum(1 for s in status_list if s == 0)
    failed = n - completed

    # Collect valid results (status == 0)
    valid_results = [r for r, s in zip(results_list, status_list) if s == 0]

    result = {
        "success": failed == 0,
        "mode": "gpu",
        "instances": n,
        "completed": completed,
        "failed": failed,
        "results": results_list,
        "stats": _stats(valid_results),
        "total_time_ms": round(elapsed_ms, 2),
    }

    # Tier 2: reconstruct per-thread output from buffer
    if is_tier2:
        counts = output_counts_out.tolist()
        raw_buf = output_buf_out.tolist()
        # Extract only the valid entries for each thread
        raw_data: list[int] = []
        for tid in range(n):
            entry_count = int(counts[tid])
            if entry_count > 0:
                base = tid * max_out_per_thread * _OUTPUT_ENTRY_FIELDS
                for e in range(entry_count):
                    offset = base + e * _OUTPUT_ENTRY_FIELDS
                    raw_data.extend(raw_buf[offset:offset + _OUTPUT_ENTRY_FIELDS])
        result["outputs"] = _reconstruct_output(
            raw_data,
            gpu_prog.string_table,
            n,
        )

    return result


# ── Auto-select GPU or CPU ──────────────────────────────────────────────

def run_auto(
    program: Program,
    n: int = 1,
    **kwargs,
) -> dict:
    """Auto-select GPU (when beneficial) or CPU fallback.

    Uses GPU when:
      - n >= 256 (enough parallelism to justify dispatch overhead)
      - GPU is available (MLX + Metal)
      - Program is tier <= 2 (no INPUT)

    Otherwise falls back to CPU execution via the agent runner.

    Returns the same dict format as ``gpu_run()`` for GPU mode, or a
    compatible dict for CPU mode.
    """
    tier = gpu_tier(program)
    use_gpu = n >= 256 and gpu_available() and tier <= 2

    if use_gpu:
        try:
            return gpu_run(program, n=n, **kwargs)
        except Exception:
            pass  # Fall through to CPU

    # CPU fallback
    from .agent import run_agent_mode
    t0 = time.perf_counter()
    agent_result = run_agent_mode(program, filename="<auto>", runs=n)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Extract numeric results from agent output
    numeric_results: list[float] = []
    for r in agent_result.get("results", []):
        if r.get("status") == "ok" and r.get("output"):
            try:
                numeric_results.append(float(r["output"].strip()))
            except (ValueError, TypeError):
                pass

    ok_count = sum(
        1 for r in agent_result.get("results", []) if r.get("status") == "ok"
    )

    return {
        "success": ok_count == n,
        "mode": "cpu",
        "instances": n,
        "completed": ok_count,
        "failed": n - ok_count,
        "results": numeric_results,
        "stats": _stats(numeric_results),
        "total_time_ms": round(elapsed_ms, 2),
    }
