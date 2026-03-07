"""Tests for the MSL GPU kernel and gpu.py module.

These tests validate source-level correctness of the Metal kernel and the
gpu.py interface without requiring actual GPU access.  All tests are pure
Python checks on the kernel source text and opcode maps.
"""

import re

import pytest

from emojiasm.gpu import (
    GPU_OPCODES,
    DEFAULT_MAX_STEPS,
    DEFAULT_STACK_DEPTH,
    DEFAULT_THREADGROUP_SIZE,
    get_kernel_source,
    validate_opcodes,
)
from emojiasm.bytecode import OP_MAP
from emojiasm.opcodes import Op


# ── Kernel source loading ────────────────────────────────────────────────

class TestGetKernelSource:
    def test_returns_string(self):
        src = get_kernel_source()
        assert isinstance(src, str)

    def test_not_empty(self):
        src = get_kernel_source()
        assert len(src) > 0

    def test_contains_kernel_function(self):
        """The source must declare the emojiasm_vm kernel function."""
        src = get_kernel_source()
        assert "kernel void emojiasm_vm" in src

    def test_contains_metal_stdlib(self):
        src = get_kernel_source()
        assert "#include <metal_stdlib>" in src

    def test_contains_using_namespace(self):
        src = get_kernel_source()
        assert "using namespace metal;" in src


# ── Buffer bindings ──────────────────────────────────────────────────────

class TestBufferBindings:
    """Verify the kernel has all required buffer bindings."""

    def test_bytecode_buffer(self):
        src = get_kernel_source()
        assert "[[buffer(0)]]" in src
        assert "bytecode" in src

    def test_constants_buffer(self):
        src = get_kernel_source()
        assert "[[buffer(1)]]" in src
        assert "constants" in src

    def test_stacks_buffer(self):
        src = get_kernel_source()
        assert "[[buffer(2)]]" in src
        assert "stacks" in src

    def test_results_buffer(self):
        src = get_kernel_source()
        assert "[[buffer(3)]]" in src
        assert "results" in src

    def test_status_buffer(self):
        src = get_kernel_source()
        assert "[[buffer(4)]]" in src
        assert "status" in src

    def test_num_insts_buffer(self):
        src = get_kernel_source()
        assert "[[buffer(5)]]" in src
        assert "num_insts" in src

    def test_stack_depth_buffer(self):
        src = get_kernel_source()
        assert "[[buffer(6)]]" in src
        assert "stack_depth" in src

    def test_max_steps_buffer(self):
        src = get_kernel_source()
        assert "[[buffer(7)]]" in src
        assert "max_steps" in src

    def test_thread_position(self):
        src = get_kernel_source()
        assert "[[thread_position_in_grid]]" in src


# ── Opcode map consistency ───────────────────────────────────────────────

class TestOpcodeConsistency:
    """Verify GPU_OPCODES matches bytecode.py OP_MAP."""

    # Mapping from GPU_OPCODES keys to Op enum names (for comparison ops)
    _REMAP = {"EQ": "CMP_EQ", "LT": "CMP_LT", "GT": "CMP_GT"}

    def test_validate_opcodes_passes(self):
        """The validate_opcodes() function should not raise."""
        validate_opcodes()

    def test_gpu_opcodes_count_matches_op_map(self):
        """GPU_OPCODES and OP_MAP should have the same number of entries."""
        assert len(GPU_OPCODES) == len(OP_MAP)

    def test_every_op_map_entry_in_gpu_opcodes(self):
        """Every bytecode.py OP_MAP entry should have a GPU_OPCODES counterpart."""
        reverse_remap = {v: k for k, v in self._REMAP.items()}
        for op, code in OP_MAP.items():
            gpu_name = reverse_remap.get(op.name, op.name)
            assert gpu_name in GPU_OPCODES, f"Missing GPU opcode for Op.{op.name}"
            assert GPU_OPCODES[gpu_name] == code, (
                f"Mismatch: GPU_OPCODES[{gpu_name!r}]=0x{GPU_OPCODES[gpu_name]:02X} "
                f"!= OP_MAP[Op.{op.name}]=0x{code:02X}"
            )

    def test_every_gpu_opcode_in_op_map(self):
        """Every GPU_OPCODES entry should correspond to a bytecode.py OP_MAP entry."""
        for gpu_name, gpu_code in GPU_OPCODES.items():
            op_name = self._REMAP.get(gpu_name, gpu_name)
            op = Op[op_name]
            assert op in OP_MAP, f"Op.{op_name} not in OP_MAP"
            assert OP_MAP[op] == gpu_code

    def test_specific_opcode_values(self):
        """Spot-check critical opcode values."""
        assert GPU_OPCODES["PUSH"] == 0x01
        assert GPU_OPCODES["HALT"] == 0x35
        assert GPU_OPCODES["ADD"] == 0x10
        assert GPU_OPCODES["JMP"] == 0x30
        assert GPU_OPCODES["CALL"] == 0x33
        assert GPU_OPCODES["STORE"] == 0x40
        assert GPU_OPCODES["LOAD"] == 0x41
        assert GPU_OPCODES["RANDOM"] == 0x60

    def test_no_duplicate_gpu_codes(self):
        """All hex values in GPU_OPCODES must be unique."""
        codes = list(GPU_OPCODES.values())
        assert len(codes) == len(set(codes))


# ── Kernel opcode cases ──────────────────────────────────────────────────

class TestKernelOpcodeCases:
    """Verify the kernel source contains switch cases for all opcodes."""

    def test_all_opcodes_have_case(self):
        """Every GPU opcode should appear as a case constant in the kernel."""
        src = get_kernel_source()
        expected_constants = {
            "PUSH": "OP_PUSH",
            "POP": "OP_POP",
            "DUP": "OP_DUP",
            "SWAP": "OP_SWAP",
            "OVER": "OP_OVER",
            "ROT": "OP_ROT",
            "ADD": "OP_ADD",
            "SUB": "OP_SUB",
            "MUL": "OP_MUL",
            "DIV": "OP_DIV",
            "MOD": "OP_MOD",
            "EQ": "OP_EQ",
            "LT": "OP_LT",
            "GT": "OP_GT",
            "AND": "OP_AND",
            "OR": "OP_OR",
            "NOT": "OP_NOT",
            "JMP": "OP_JMP",
            "JZ": "OP_JZ",
            "JNZ": "OP_JNZ",
            "CALL": "OP_CALL",
            "RET": "OP_RET",
            "HALT": "OP_HALT",
            "NOP": "OP_NOP",
            "STORE": "OP_STORE",
            "LOAD": "OP_LOAD",
            "PRINT": "OP_PRINT",
            "PRINTLN": "OP_PRINTLN",
            "RANDOM": "OP_RANDOM",
        }
        for gpu_name, msl_const in expected_constants.items():
            # Check the constant is defined
            assert f"constant uint8_t {msl_const}" in src, (
                f"Missing MSL constant definition for {msl_const}"
            )
            # Check a case statement references it
            assert f"case {msl_const}:" in src, (
                f"Missing case {msl_const}: in switch dispatch"
            )

    def test_opcode_hex_values_in_kernel(self):
        """Verify hex values in the kernel match GPU_OPCODES."""
        src = get_kernel_source()
        for gpu_name, code in GPU_OPCODES.items():
            # Map GPU name to MSL constant name
            msl_name = f"OP_{gpu_name}"
            # Find the constant definition line
            hex_str = f"0x{code:02X}" if code < 0x100 else f"0x{code:02x}"
            # The kernel uses lowercase hex in some cases; check both
            pattern = rf"constant\s+uint8_t\s+{msl_name}\s*=\s*0x{code:02X}"
            match = re.search(pattern, src, re.IGNORECASE)
            assert match is not None, (
                f"Constant {msl_name} not defined with value 0x{code:02X} in kernel"
            )


# ── RANDOM opcode ────────────────────────────────────────────────────────

class TestRandomOpcode:
    """Verify the RANDOM opcode implementation in the kernel."""

    def test_random_case_exists(self):
        src = get_kernel_source()
        assert "case OP_RANDOM:" in src

    def test_random_opcode_value(self):
        assert GPU_OPCODES["RANDOM"] == 0x60
        assert OP_MAP[Op.RANDOM] == 0x60

    def test_philox_prng_in_kernel(self):
        """The kernel should implement Philox-4x32-10 PRNG."""
        src = get_kernel_source()
        assert "philox" in src.lower() or "Philox" in src
        assert "PhiloxState" in src

    def test_philox_round_count(self):
        """Philox-4x32-10 requires 10 rounds."""
        src = get_kernel_source()
        assert "philox4x32_10" in src

    def test_random_seeds_with_thread_id(self):
        """PRNG should be seeded with the thread ID for unique streams."""
        src = get_kernel_source()
        # The key should incorporate tid
        assert "tid" in src
        # Look for key initialization with tid
        assert re.search(r"key\[0\]\s*=\s*tid", src) is not None


# ── Constants ────────────────────────────────────────────────────────────

class TestConstants:
    def test_default_stack_depth(self):
        assert DEFAULT_STACK_DEPTH == 128

    def test_default_max_steps(self):
        assert DEFAULT_MAX_STEPS == 1_000_000

    def test_default_threadgroup_size(self):
        assert DEFAULT_THREADGROUP_SIZE == 256


# ── Kernel structure ─────────────────────────────────────────────────────

class TestKernelStructure:
    """Validate structural properties of the kernel source."""

    def test_has_status_codes(self):
        """Kernel should define status code constants."""
        src = get_kernel_source()
        assert "STATUS_OK" in src
        assert "STATUS_ERROR" in src
        assert "STATUS_DIV_ZERO" in src
        assert "STATUS_TIMEOUT" in src

    def test_status_values(self):
        """Status codes should match documented values."""
        src = get_kernel_source()
        assert re.search(r"STATUS_OK\s*=\s*0", src)
        assert re.search(r"STATUS_ERROR\s*=\s*1", src)
        assert re.search(r"STATUS_DIV_ZERO\s*=\s*2", src)
        assert re.search(r"STATUS_TIMEOUT\s*=\s*3", src)

    def test_has_call_stack(self):
        """Kernel should define a call stack."""
        src = get_kernel_source()
        assert "call_stack" in src
        assert "CALL_STACK_DEPTH" in src

    def test_has_memory_cells(self):
        """Kernel should define memory cells."""
        src = get_kernel_source()
        assert "memory" in src
        assert "NUM_MEMORY_CELLS" in src

    def test_has_default_case(self):
        """Switch should have a default case for unknown opcodes."""
        src = get_kernel_source()
        assert "default:" in src

    def test_div_zero_protection(self):
        """DIV and MOD should check for division by zero."""
        src = get_kernel_source()
        # The kernel should check for zero before dividing
        assert "STATUS_DIV_ZERO" in src

    def test_timeout_protection(self):
        """Kernel should have timeout/step-limit protection."""
        src = get_kernel_source()
        assert "max_steps" in src
        assert "STATUS_TIMEOUT" in src

    def test_result_written(self):
        """Kernel should write TOS to results buffer."""
        src = get_kernel_source()
        assert "results[tid]" in src
