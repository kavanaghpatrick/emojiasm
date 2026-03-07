"""Tests for the GPU bytecode compiler (emojiasm/bytecode.py)."""

import pytest
from emojiasm.parser import parse, Program, Function, Instruction
from emojiasm.opcodes import Op
from emojiasm.bytecode import (
    compile_to_bytecode,
    gpu_tier,
    GpuProgram,
    OP_MAP,
    OPCODE_TO_OP,
    BytecodeError,
    _pack,
    _unpack,
    _build_constant_pool,
    _build_memory_map,
    _flatten_functions,
    _analyze_max_stack_depth,
    _GPU_MAX_STACK,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _parse(source: str) -> Program:
    """Parse source without running the VM."""
    return parse(source)


def _decode_bytecode(bytecode: list[int]) -> list[tuple[int, int]]:
    """Unpack a bytecode list into (opcode, operand) pairs."""
    return [_unpack(word) for word in bytecode]


# ── Pack / Unpack ─────────────────────────────────────────────────────────

class TestPackUnpack:
    def test_pack_basic(self):
        word = _pack(0x01, 42)
        assert word == (0x01 << 24) | 42

    def test_pack_zero_operand(self):
        word = _pack(0x35, 0)
        assert word == 0x35 << 24

    def test_pack_max_operand(self):
        word = _pack(0xFF, 0xFFFFFF)
        assert word == 0xFFFFFFFF

    def test_unpack_roundtrip(self):
        for opcode in [0x01, 0x10, 0x30, 0xFF]:
            for operand in [0, 1, 42, 0xFFFFFF]:
                op, arg = _unpack(_pack(opcode, operand))
                assert op == opcode
                assert arg == operand

    def test_pack_negative_operand_raises(self):
        with pytest.raises(ValueError):
            _pack(0x01, -1)

    def test_pack_overflow_operand_raises(self):
        with pytest.raises(ValueError):
            _pack(0x01, 0x1000000)


# ── Simple program encoding ──────────────────────────────────────────────

class TestSimpleEncoding:
    """Encode PUSH 6, PUSH 7, MUL, PRINTLN, HALT — verify bytecode."""

    def test_simple_program(self):
        src = "📥 6\n📥 7\n✖️\n🖨️\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        assert isinstance(gpu, GpuProgram)
        assert len(gpu.bytecode) == 5

        decoded = _decode_bytecode(gpu.bytecode)

        # PUSH 6 -> opcode 0x01, operand = index of 6.0 in constant pool
        assert decoded[0][0] == OP_MAP[Op.PUSH]
        # PUSH 7 -> opcode 0x01, operand = index of 7.0 in constant pool
        assert decoded[1][0] == OP_MAP[Op.PUSH]
        # MUL -> opcode 0x12, operand 0
        assert decoded[2] == (OP_MAP[Op.MUL], 0)
        # PRINTLN -> opcode 0x51, operand 0
        assert decoded[3] == (OP_MAP[Op.PRINTLN], 0)
        # HALT -> opcode 0x35, operand 0
        assert decoded[4] == (OP_MAP[Op.HALT], 0)

    def test_push_operands_are_pool_indices(self):
        src = "📥 6\n📥 7\n✖️\n🖨️\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        idx_6 = gpu.constants.index(6.0)
        idx_7 = gpu.constants.index(7.0)

        assert decoded[0] == (OP_MAP[Op.PUSH], idx_6)
        assert decoded[1] == (OP_MAP[Op.PUSH], idx_7)

    def test_constants_contain_values(self):
        src = "📥 6\n📥 7\n✖️\n🖨️\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        assert 6.0 in gpu.constants
        assert 7.0 in gpu.constants

    def test_entry_offset_is_zero(self):
        src = "📥 42\n🖨️\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)
        assert gpu.entry_offset == 0

    def test_num_functions(self):
        src = "📥 42\n🖨️\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)
        assert gpu.num_functions == 1


# ── Constant pool deduplication ───────────────────────────────────────────

class TestConstantPool:
    def test_deduplication(self):
        """Same literal used twice gets a single pool entry."""
        src = "📥 42\n📥 42\n➕\n🖨️\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        assert gpu.constants.count(42.0) == 1

        decoded = _decode_bytecode(gpu.bytecode)
        # Both PUSH instructions should reference the same pool index
        assert decoded[0][1] == decoded[1][1]

    def test_multiple_distinct_values(self):
        src = "📥 1\n📥 2\n📥 3\n➕\n➕\n🖨️\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        assert len(gpu.constants) == 3
        assert set(gpu.constants) == {1.0, 2.0, 3.0}

    def test_float_constants(self):
        src = "📥 3.14\n📥 2.72\n➕\n🖨️\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        assert 3.14 in gpu.constants
        assert 2.72 in gpu.constants

    def test_int_and_float_same_value_deduplicated(self):
        """int 5 and float 5.0 should map to the same pool entry."""
        src = "📥 5\n📥 5.0\n➕\n🖨️\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        assert gpu.constants.count(5.0) == 1

    def test_build_constant_pool_standalone(self):
        insts = [
            Instruction(Op.PUSH, 10),
            Instruction(Op.PUSH, 20),
            Instruction(Op.PUSH, 10),
            Instruction(Op.ADD),
        ]
        pool_map, pool = _build_constant_pool(insts)
        assert len(pool) == 2
        assert pool_map[10.0] == 0
        assert pool_map[20.0] == 1


# ── Function flattening ──────────────────────────────────────────────────

class TestFunctionFlattening:
    def test_entry_first(self):
        """Entry function appears at offset 0 in flattened bytecode."""
        src = (
            "📜 helper\n📥 1\n📲\n"
            "📜 🏠\n📞 helper\n🛑\n"
        )
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        # Entry (🏠) should be at offset 0
        assert gpu.entry_offset == 0

        decoded = _decode_bytecode(gpu.bytecode)
        # First instruction should be CALL (from entry)
        assert decoded[0][0] == OP_MAP[Op.CALL]

    def test_multi_function_offsets(self):
        src = (
            "📜 helper\n📥 99\n📲\n"
            "📜 🏠\n📞 helper\n🛑\n"
        )
        prog = _parse(src)
        flat, func_offsets, _ = _flatten_functions(prog)

        # 🏠 has 2 instructions: CALL, HALT
        # helper has 2 instructions: PUSH, RET
        assert func_offsets["🏠"] == 0
        assert func_offsets["helper"] == 2

    def test_call_operand_is_bytecode_offset(self):
        """CALL operand should be rewritten to the callee's bytecode offset."""
        src = (
            "📜 helper\n📥 99\n📲\n"
            "📜 🏠\n📞 helper\n🛑\n"
        )
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        # Find the CALL instruction
        call_insts = [(i, op, arg) for i, (op, arg) in enumerate(decoded)
                      if op == OP_MAP[Op.CALL]]
        assert len(call_insts) == 1
        _, _, call_operand = call_insts[0]

        # The helper function starts after the 2 entry instructions
        assert call_operand == 2

    def test_three_functions(self):
        src = (
            "📜 f1\n📥 1\n📲\n"
            "📜 f2\n📥 2\n📲\n"
            "📜 🏠\n📞 f1\n📞 f2\n🛑\n"
        )
        prog = _parse(src)
        flat, func_offsets, _ = _flatten_functions(prog)

        # Entry (🏠) first with 3 instructions
        assert func_offsets["🏠"] == 0
        # f1 next with 2 instructions
        assert func_offsets["f1"] == 3
        # f2 next with 2 instructions
        assert func_offsets["f2"] == 5


# ── Label resolution ─────────────────────────────────────────────────────

class TestLabelResolution:
    def test_jmp_resolved(self):
        src = (
            "📜 🏠\n"
            "🏷️ start\n"
            "📥 1\n"
            "👉 start\n"
        )
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        # JMP should point to offset 0 (label 'start' is at instruction 0)
        jmp_inst = decoded[1]  # second instruction
        assert jmp_inst[0] == OP_MAP[Op.JMP]
        assert jmp_inst[1] == 0  # label 'start' -> offset 0

    def test_jz_resolved(self):
        src = (
            "📜 🏠\n"
            "📥 0\n"
            "🤔 end\n"
            "📥 42\n"
            "🖨️\n"
            "🏷️ end\n"
            "🛑\n"
        )
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        # JZ should point to the HALT at offset 4
        jz_inst = decoded[1]
        assert jz_inst[0] == OP_MAP[Op.JZ]
        assert jz_inst[1] == 4  # label 'end' is before the 5th instruction (index 4)

    def test_jnz_resolved(self):
        src = (
            "📜 🏠\n"
            "📥 1\n"
            "😤 skip\n"
            "📥 0\n"
            "🏷️ skip\n"
            "🛑\n"
        )
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        jnz_inst = decoded[1]
        assert jnz_inst[0] == OP_MAP[Op.JNZ]
        assert jnz_inst[1] == 3  # label 'skip' -> offset 3

    def test_label_in_non_entry_function(self):
        """Labels in non-entry functions get absolute offsets."""
        src = (
            "📜 loopy\n"
            "🏷️ top\n"
            "📥 1\n"
            "👉 top\n"
            "📜 🏠\n"
            "📞 loopy\n"
            "🛑\n"
        )
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        # Entry (🏠) is first: CALL(2), HALT => offsets 0, 1
        # loopy starts at offset 2: PUSH(1), JMP(2) => offsets 2, 3
        # JMP should point to offset 2 (absolute position of 'top')
        jmp_inst = decoded[3]  # 4th instruction overall
        assert jmp_inst[0] == OP_MAP[Op.JMP]
        assert jmp_inst[1] == 2


# ── Memory cell mapping ──────────────────────────────────────────────────

class TestMemoryMapping:
    def test_basic_mapping(self):
        src = (
            "📜 🏠\n"
            "📥 10\n"
            "💾 x\n"
            "📂 x\n"
            "🖨️\n"
            "🛑\n"
        )
        prog = _parse(src)
        mem_map = _build_memory_map(prog)
        assert "x" in mem_map
        assert mem_map["x"] == 0

    def test_multiple_cells_sorted(self):
        src = (
            "📜 🏠\n"
            "📥 1\n💾 z\n"
            "📥 2\n💾 a\n"
            "📥 3\n💾 m\n"
            "🛑\n"
        )
        prog = _parse(src)
        mem_map = _build_memory_map(prog)
        # Sorted alphabetically: a=0, m=1, z=2
        assert mem_map["a"] == 0
        assert mem_map["m"] == 1
        assert mem_map["z"] == 2

    def test_store_load_operands_are_cell_indices(self):
        src = (
            "📜 🏠\n"
            "📥 10\n"
            "💾 val\n"
            "📂 val\n"
            "🖨️\n"
            "🛑\n"
        )
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)
        mem_map = _build_memory_map(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        # STORE should have operand = cell index of 'val'
        store_inst = decoded[1]
        assert store_inst[0] == OP_MAP[Op.STORE]
        assert store_inst[1] == mem_map["val"]

        # LOAD should have same cell index
        load_inst = decoded[2]
        assert load_inst[0] == OP_MAP[Op.LOAD]
        assert load_inst[1] == mem_map["val"]

    def test_cells_across_functions(self):
        src = (
            "📜 helper\n📥 5\n💾 shared\n📲\n"
            "📜 🏠\n📂 shared\n🖨️\n🛑\n"
        )
        prog = _parse(src)
        mem_map = _build_memory_map(prog)
        assert "shared" in mem_map


# ── GPU tier classification ──────────────────────────────────────────────

class TestGpuTier:
    def test_tier1_numeric_only(self):
        """No I/O at all -> tier 1."""
        src = "📜 🏠\n📥 6\n📥 7\n✖️\n🛑"
        prog = _parse(src)
        assert gpu_tier(prog) == 1

    def test_tier2_with_output(self):
        """PRINT/PRINTLN but no INPUT -> tier 2."""
        src = "📜 🏠\n📥 42\n🖨️\n🛑"
        prog = _parse(src)
        assert gpu_tier(prog) == 2

    def test_tier2_with_print(self):
        src = "📜 🏠\n📥 42\n📢\n🛑"
        prog = _parse(src)
        assert gpu_tier(prog) == 2

    def test_tier3_with_input(self):
        """INPUT requires CPU fallback -> tier 3."""
        src = "📜 🏠\n🎤\n🛑"
        prog = _parse(src)
        assert gpu_tier(prog) == 3

    def test_tier3_with_input_num(self):
        src = "📜 🏠\n🔟\n🛑"
        prog = _parse(src)
        assert gpu_tier(prog) == 3

    def test_tier3_with_strings(self):
        """String operations require CPU fallback -> tier 3."""
        src = '📜 🏠\n💬 "hello"\n📢\n🛑'
        prog = _parse(src)
        assert gpu_tier(prog) == 3

    def test_tier_in_gpu_program(self):
        """gpu_tier result should match GpuProgram.gpu_tier."""
        src = "📜 🏠\n📥 42\n🖨️\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)
        assert gpu.gpu_tier == gpu_tier(prog)
        assert gpu.gpu_tier == 2


# ── Stack depth analysis ─────────────────────────────────────────────────

class TestStackDepth:
    def test_simple_depth(self):
        """PUSH, PUSH, MUL -> max depth 2."""
        src = "📥 6\n📥 7\n✖️\n🖨️\n🛑"
        prog = _parse(src)
        depth = _analyze_max_stack_depth(prog)
        assert depth == 2

    def test_deeper_stack(self):
        """Four pushes then operations -> max depth 4."""
        src = "📥 1\n📥 2\n📥 3\n📥 4\n➕\n➕\n➕\n🖨️\n🛑"
        prog = _parse(src)
        depth = _analyze_max_stack_depth(prog)
        assert depth == 4

    def test_dup_increases_depth(self):
        src = "📥 1\n📋\n📋\n🛑"
        prog = _parse(src)
        depth = _analyze_max_stack_depth(prog)
        assert depth == 3  # PUSH(1) + DUP(2) + DUP(3)

    def test_capped_at_128(self):
        """Stack depth should never exceed GPU max of 128 (KB #147)."""
        # Create a program with 200 PUSHes
        lines = ["📜 🏠"] + ["📥 1"] * 200 + ["🛑"]
        src = "\n".join(lines)
        prog = _parse(src)
        depth = _analyze_max_stack_depth(prog)
        assert depth == _GPU_MAX_STACK
        assert depth == 128

    def test_max_stack_depth_in_gpu_program(self):
        src = "📥 6\n📥 7\n✖️\n🖨️\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)
        assert gpu.max_stack_depth == 2

    def test_over_increases_depth(self):
        src = "📥 1\n📥 2\n🫴\n🛑"
        prog = _parse(src)
        depth = _analyze_max_stack_depth(prog)
        assert depth == 3  # PUSH(1) + PUSH(2) + OVER(3)


# ── Round-trip verification ──────────────────────────────────────────────

class TestRoundTrip:
    def test_decode_all_opcodes(self):
        """Every packed opcode should decode back to the correct Op."""
        for op, code in OP_MAP.items():
            word = _pack(code, 0)
            decoded_code, decoded_operand = _unpack(word)
            assert decoded_code == code
            assert OPCODE_TO_OP[decoded_code] == op

    def test_roundtrip_simple_program(self):
        """Encode -> decode should preserve instruction sequence."""
        src = "📥 10\n📥 20\n➕\n🖨️\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        expected_ops = [Op.PUSH, Op.PUSH, Op.ADD, Op.PRINTLN, Op.HALT]
        for (opcode, _), expected_op in zip(decoded, expected_ops):
            assert OPCODE_TO_OP[opcode] == expected_op

    def test_roundtrip_constant_values(self):
        """Constants should be retrievable from the pool via operand index."""
        src = "📥 3.14\n📥 2.72\n➕\n🛑"
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        # First PUSH operand -> pool index -> value should be 3.14
        val1 = gpu.constants[decoded[0][1]]
        val2 = gpu.constants[decoded[1][1]]
        assert val1 == pytest.approx(3.14)
        assert val2 == pytest.approx(2.72)

    def test_roundtrip_with_functions(self):
        """Multi-function program should round-trip correctly."""
        src = (
            "📜 double_it\n📋\n➕\n📲\n"
            "📜 🏠\n📥 21\n📞 double_it\n🖨️\n🛑\n"
        )
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        # Entry is first: PUSH(21), CALL(double_it), PRINTLN, HALT
        # Then double_it: DUP, ADD, RET
        expected_ops = [
            Op.PUSH, Op.CALL, Op.PRINTLN, Op.HALT,
            Op.DUP, Op.ADD, Op.RET,
        ]
        assert len(decoded) == len(expected_ops)
        for (opcode, _), expected_op in zip(decoded, expected_ops):
            assert OPCODE_TO_OP[opcode] == expected_op


# ── Error handling ────────────────────────────────────────────────────────

class TestErrors:
    def test_unsupported_opcode_raises(self):
        """Ops not in OP_MAP should raise BytecodeError."""
        # Create a program with PRINTS (not in OP_MAP)
        prog = Program()
        func = Function(name="🏠")
        func.instructions.append(Instruction(Op.PRINTS, "hello"))
        prog.functions["🏠"] = func
        prog.entry_point = "🏠"

        with pytest.raises(BytecodeError, match="not supported"):
            compile_to_bytecode(prog)

    def test_string_push_raises(self):
        """PUSH with string arg should raise BytecodeError."""
        prog = Program()
        func = Function(name="🏠")
        func.instructions.append(Instruction(Op.PUSH, "hello"))
        func.instructions.append(Instruction(Op.HALT))
        prog.functions["🏠"] = func
        prog.entry_point = "🏠"

        with pytest.raises(BytecodeError, match="non-numeric"):
            compile_to_bytecode(prog)


# ── OP_MAP completeness ──────────────────────────────────────────────────

class TestOpMap:
    def test_no_duplicate_opcodes(self):
        """Each Op should map to a unique uint8 opcode."""
        codes = list(OP_MAP.values())
        assert len(codes) == len(set(codes))

    def test_opcodes_fit_in_8_bits(self):
        """All opcodes should fit in 8 bits."""
        for code in OP_MAP.values():
            assert 0 <= code <= 0xFF

    def test_expected_opcodes_present(self):
        """Key opcodes from the issue spec should be present."""
        assert Op.PUSH in OP_MAP
        assert Op.HALT in OP_MAP
        assert Op.CALL in OP_MAP
        assert Op.RET in OP_MAP
        assert Op.JMP in OP_MAP
        assert Op.STORE in OP_MAP
        assert Op.LOAD in OP_MAP

    def test_reverse_map_completeness(self):
        """OPCODE_TO_OP should reverse OP_MAP exactly."""
        for op, code in OP_MAP.items():
            assert OPCODE_TO_OP[code] == op


# ── Integration: full programs ────────────────────────────────────────────

class TestIntegration:
    def test_fibonacci_style(self):
        """A loop-based program compiles without error."""
        src = (
            "📜 🏠\n"
            "📥 0\n💾 a\n"
            "📥 1\n💾 b\n"
            "📥 10\n💾 n\n"
            "🏷️ loop\n"
            "📂 n\n📥 0\n🟰\n🤔 done\n"
            "📂 a\n🖨️\n"
            "📂 a\n📂 b\n➕\n💾 temp\n"
            "📂 b\n💾 a\n"
            "📂 temp\n💾 b\n"
            "📂 n\n📥 1\n➖\n💾 n\n"
            "👉 loop\n"
            "🏷️ done\n"
            "🛑\n"
        )
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        assert gpu.gpu_tier == 2  # has PRINTLN
        assert gpu.num_functions == 1
        assert gpu.entry_offset == 0
        assert len(gpu.bytecode) > 0
        assert len(gpu.constants) > 0

    def test_all_arithmetic_ops(self):
        """All arithmetic opcodes encode correctly."""
        src = (
            "📥 10\n📥 3\n➕\n📤\n"
            "📥 10\n📥 3\n➖\n📤\n"
            "📥 10\n📥 3\n✖️\n📤\n"
            "📥 10\n📥 3\n➗\n📤\n"
            "📥 10\n📥 3\n🔢\n📤\n"
            "🛑"
        )
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        opcodes = [op for op, _ in decoded]

        assert OP_MAP[Op.ADD] in opcodes
        assert OP_MAP[Op.SUB] in opcodes
        assert OP_MAP[Op.MUL] in opcodes
        assert OP_MAP[Op.DIV] in opcodes
        assert OP_MAP[Op.MOD] in opcodes

    def test_comparison_and_logic_ops(self):
        """Comparison and logic opcodes encode correctly."""
        src = (
            "📥 1\n📥 2\n🟰\n📤\n"
            "📥 1\n📥 2\n📏\n📤\n"
            "📥 1\n📥 2\n📐\n📤\n"
            "📥 1\n📥 1\n🤝\n📤\n"
            "📥 1\n📥 0\n🤙\n📤\n"
            "📥 1\n🚫\n📤\n"
            "🛑"
        )
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        opcodes = [op for op, _ in decoded]

        assert OP_MAP[Op.CMP_EQ] in opcodes
        assert OP_MAP[Op.CMP_LT] in opcodes
        assert OP_MAP[Op.CMP_GT] in opcodes
        assert OP_MAP[Op.AND] in opcodes
        assert OP_MAP[Op.OR] in opcodes
        assert OP_MAP[Op.NOT] in opcodes

    def test_stack_ops(self):
        """Stack manipulation opcodes encode correctly."""
        src = (
            "📥 1\n📋\n"      # DUP
            "📥 2\n🔀\n"      # SWAP
            "📥 3\n🫴\n"      # OVER
            "🔄\n"            # ROT
            "📤\n📤\n📤\n📤\n"
            "🛑"
        )
        prog = _parse(src)
        gpu = compile_to_bytecode(prog)

        decoded = _decode_bytecode(gpu.bytecode)
        opcodes = [op for op, _ in decoded]

        assert OP_MAP[Op.DUP] in opcodes
        assert OP_MAP[Op.SWAP] in opcodes
        assert OP_MAP[Op.OVER] in opcodes
        assert OP_MAP[Op.ROT] in opcodes
