"""Comprehensive parser tests for EmojiASM."""

import pytest
from emojiasm.parser import parse, ParseError
from emojiasm.opcodes import Op


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _func(program, name="🏠"):
    """Return the named Function from a parsed Program."""
    return program.functions[name]


def _instr(program, index=0, func_name="🏠"):
    """Return a single Instruction by index from a function."""
    return _func(program, func_name).instructions[index]


# ---------------------------------------------------------------------------
# 1. PUSH argument parsing
# ---------------------------------------------------------------------------

class TestPushParsing:

    def test_push_positive_integer(self):
        prog = parse("📜 🏠\n  📥 42\n  🛑")
        assert _instr(prog).op == Op.PUSH
        assert _instr(prog).arg == 42
        assert isinstance(_instr(prog).arg, int)

    def test_push_zero(self):
        prog = parse("📜 🏠\n  📥 0\n  🛑")
        assert _instr(prog).arg == 0

    def test_push_negative_integer(self):
        prog = parse("📜 🏠\n  📥 -7\n  🛑")
        assert _instr(prog).arg == -7
        assert isinstance(_instr(prog).arg, int)

    def test_push_large_integer(self):
        prog = parse("📜 🏠\n  📥 1000000\n  🛑")
        assert _instr(prog).arg == 1_000_000

    def test_push_hex_lowercase(self):
        prog = parse("📜 🏠\n  📥 0xff\n  🛑")
        assert _instr(prog).arg == 255
        assert isinstance(_instr(prog).arg, int)

    def test_push_hex_uppercase_prefix(self):
        prog = parse("📜 🏠\n  📥 0xFF\n  🛑")
        assert _instr(prog).arg == 255

    def test_push_hex_uppercase_X(self):
        prog = parse("📜 🏠\n  📥 0XFF\n  🛑")
        assert _instr(prog).arg == 255

    def test_push_hex_zero(self):
        prog = parse("📜 🏠\n  📥 0x0\n  🛑")
        assert _instr(prog).arg == 0

    def test_push_binary_lowercase(self):
        prog = parse("📜 🏠\n  📥 0b101\n  🛑")
        assert _instr(prog).arg == 5
        assert isinstance(_instr(prog).arg, int)

    def test_push_binary_uppercase_B(self):
        prog = parse("📜 🏠\n  📥 0B1010\n  🛑")
        assert _instr(prog).arg == 10

    def test_push_float(self):
        prog = parse("📜 🏠\n  📥 3.14\n  🛑")
        assert abs(_instr(prog).arg - 3.14) < 1e-9
        assert isinstance(_instr(prog).arg, float)

    def test_push_negative_float(self):
        prog = parse("📜 🏠\n  📥 -2.718\n  🛑")
        assert abs(_instr(prog).arg - (-2.718)) < 1e-9
        assert isinstance(_instr(prog).arg, float)

    def test_push_float_zero(self):
        prog = parse("📜 🏠\n  📥 0.0\n  🛑")
        assert _instr(prog).arg == 0.0
        assert isinstance(_instr(prog).arg, float)

    def test_push_string_double_quotes(self):
        prog = parse('📜 🏠\n  📥 "hello"\n  🛑')
        assert _instr(prog).arg == "hello"
        assert isinstance(_instr(prog).arg, str)

    def test_push_string_single_quotes(self):
        prog = parse("📜 🏠\n  📥 'world'\n  🛑")
        assert _instr(prog).arg == "world"

    def test_push_string_guillemet_quotes(self):
        prog = parse("📜 🏠\n  📥 «bonjour»\n  🛑")
        assert _instr(prog).arg == "bonjour"

    def test_push_string_empty_double_quotes(self):
        prog = parse('📜 🏠\n  📥 ""\n  🛑')
        assert _instr(prog).arg == ""

    def test_push_string_empty_single_quotes(self):
        prog = parse("📜 🏠\n  📥 ''\n  🛑")
        assert _instr(prog).arg == ""

    def test_push_string_with_spaces(self):
        prog = parse('📜 🏠\n  📥 "hello world"\n  🛑')
        assert _instr(prog).arg == "hello world"

    def test_push_escape_newline(self):
        prog = parse('📜 🏠\n  📥 "line1\\nline2"\n  🛑')
        assert _instr(prog).arg == "line1\nline2"

    def test_push_escape_tab(self):
        prog = parse('📜 🏠\n  📥 "col1\\tcol2"\n  🛑')
        assert _instr(prog).arg == "col1\tcol2"

    def test_push_escape_backslash(self):
        prog = parse('📜 🏠\n  📥 "a\\\\b"\n  🛑')
        assert _instr(prog).arg == "a\\b"

    def test_push_escape_quote_in_double_quotes(self):
        prog = parse('📜 🏠\n  📥 "say \\"hi\\""\n  🛑')
        assert _instr(prog).arg == 'say "hi"'

    def test_push_single_quote_escape(self):
        prog = parse("📜 🏠\n  📥 'it\\'s'\n  🛑")
        assert _instr(prog).arg == "it's"


# ---------------------------------------------------------------------------
# 2. Label resolution
# ---------------------------------------------------------------------------

class TestLabelResolution:

    def test_label_maps_to_instruction_after_it(self):
        # 🏷️ loop is defined after 2 instructions (📥 0, 📥 1), so index = 2
        source = "📜 🏠\n  📥 0\n  📥 1\n🏷️ loop\n  📥 2\n  🛑"
        prog = parse(source)
        func = _func(prog)
        assert func.labels["loop"] == 2

    def test_label_at_start_of_function(self):
        source = "📜 🏠\n🏷️ top\n  📥 99\n  🛑"
        prog = parse(source)
        assert _func(prog).labels["top"] == 0

    def test_label_at_end_maps_to_len_of_instructions(self):
        source = "📜 🏠\n  📥 1\n  📥 2\n🏷️ done"
        prog = parse(source)
        # No instructions follow the label, so index equals len(instructions)
        assert _func(prog).labels["done"] == 2

    def test_multiple_labels_in_one_function(self):
        source = "📜 🏠\n🏷️ a\n  📥 0\n🏷️ b\n  📥 1\n🏷️ c\n  🛑"
        prog = parse(source)
        labels = _func(prog).labels
        assert labels["a"] == 0
        assert labels["b"] == 1
        assert labels["c"] == 2

    def test_label_alt_directive(self):
        """🏷 (without variation selector) also defines a label."""
        source = "📜 🏠\n  📥 5\n🏷 myLabel\n  🛑"
        prog = parse(source)
        assert _func(prog).labels["myLabel"] == 1

    def test_label_emoji_name(self):
        source = "📜 🏠\n🏷️ 🔁\n  🛑"
        prog = parse(source)
        assert "🔁" in _func(prog).labels
        assert _func(prog).labels["🔁"] == 0


# ---------------------------------------------------------------------------
# 3. Functions: multiple functions, entry_point set to 🏠
# ---------------------------------------------------------------------------

class TestFunctions:

    def test_single_home_function(self):
        prog = parse("📜 🏠\n  🛑")
        assert "🏠" in prog.functions
        assert prog.entry_point == "🏠"

    def test_multiple_functions_parsed(self):
        source = "📜 🏠\n  📞 🔲\n  🛑\n📜 🔲\n  📲"
        prog = parse(source)
        assert "🏠" in prog.functions
        assert "🔲" in prog.functions
        assert len(prog.functions) == 2

    def test_entry_point_is_home(self):
        source = "📜 🏠\n  🛑\n📜 other\n  📲"
        prog = parse(source)
        assert prog.entry_point == "🏠"

    def test_functions_contain_correct_instructions(self):
        source = "📜 🏠\n  📥 1\n  🛑\n📜 helper\n  📥 2\n  📲"
        prog = parse(source)
        assert len(prog.functions["🏠"].instructions) == 2
        assert len(prog.functions["helper"].instructions) == 2

    def test_function_name_is_emoji(self):
        source = "📜 🔽\n  📲"
        prog = parse(source)
        assert "🔽" in prog.functions

    def test_function_name_is_word(self):
        source = "📜 fibonacci\n  📲"
        prog = parse(source)
        assert "fibonacci" in prog.functions


# ---------------------------------------------------------------------------
# 4. No 🏠 function → first defined function becomes entry_point
# ---------------------------------------------------------------------------

class TestEntryPointFallback:

    def test_no_home_first_function_is_entry_point(self):
        source = "📜 start\n  🛑"
        prog = parse(source)
        assert prog.entry_point == "start"

    def test_no_home_with_multiple_functions_first_wins(self):
        source = "📜 alpha\n  📲\n📜 beta\n  🛑"
        prog = parse(source)
        assert prog.entry_point == "alpha"

    def test_home_present_overrides_first_function(self):
        source = "📜 other\n  📲\n📜 🏠\n  🛑"
        prog = parse(source)
        assert prog.entry_point == "🏠"


# ---------------------------------------------------------------------------
# 5. Comments are ignored
# ---------------------------------------------------------------------------

class TestComments:

    def test_comment_line_skipped(self):
        source = "📜 🏠\n  💭 This is a comment\n  📥 7\n  🛑"
        prog = parse(source)
        # Only 📥 and 🛑 should be parsed; comment must be absent
        assert len(_func(prog).instructions) == 2
        assert _instr(prog, 0).op == Op.PUSH

    def test_comment_at_start_of_program(self):
        source = "💭 header comment\n📜 🏠\n  🛑"
        prog = parse(source)
        assert "🏠" in prog.functions

    def test_multiple_comments(self):
        source = "📜 🏠\n  💭 one\n  💭 two\n  📥 1\n  💭 three\n  🛑"
        prog = parse(source)
        assert len(_func(prog).instructions) == 2

    def test_comment_does_not_affect_line_numbers(self):
        # 📥 5 is on raw line 4 (1-based), comment is line 3
        source = "📜 🏠\n  💭 skip me\n  📥 5\n  🛑"
        prog = parse(source)
        push_instr = _instr(prog, 0)
        assert push_instr.line_num == 3


# ---------------------------------------------------------------------------
# 6. Blank lines are ignored
# ---------------------------------------------------------------------------

class TestBlankLines:

    def test_blank_lines_ignored(self):
        source = "📜 🏠\n\n  📥 3\n\n  🛑\n"
        prog = parse(source)
        assert len(_func(prog).instructions) == 2

    def test_only_whitespace_lines_ignored(self):
        source = "📜 🏠\n   \n  📥 1\n\t\n  🛑"
        prog = parse(source)
        assert len(_func(prog).instructions) == 2

    def test_blank_lines_between_functions(self):
        source = "📜 🏠\n  🛑\n\n\n📜 other\n  📲"
        prog = parse(source)
        assert len(prog.functions) == 2


# ---------------------------------------------------------------------------
# 7. Error: label outside function raises ParseError
# ---------------------------------------------------------------------------

class TestErrorLabelOutsideFunction:

    def test_label_before_any_function_raises(self):
        with pytest.raises(ParseError):
            parse("🏷️ orphan\n📜 🏠\n  🛑")

    def test_label_alt_before_any_function_raises(self):
        with pytest.raises(ParseError):
            parse("🏷 orphan\n📜 🏠\n  🛑")

    def test_error_contains_line_info(self):
        with pytest.raises(ParseError) as exc_info:
            parse("🏷️ orphan\n📜 🏠\n  🛑")
        assert exc_info.value.line_num == 1


# ---------------------------------------------------------------------------
# 8. Error: empty label name raises ParseError
# ---------------------------------------------------------------------------

class TestErrorEmptyLabelName:

    def test_empty_label_name_raises(self):
        with pytest.raises(ParseError):
            parse("📜 🏠\n  🏷️\n  🛑")

    def test_whitespace_only_label_name_raises(self):
        with pytest.raises(ParseError):
            parse("📜 🏠\n  🏷️   \n  🛑")

    def test_empty_alt_label_name_raises(self):
        with pytest.raises(ParseError):
            parse("📜 🏠\n  🏷\n  🛑")


# ---------------------------------------------------------------------------
# 9. Error: unknown instruction raises ParseError
# ---------------------------------------------------------------------------

class TestErrorUnknownInstruction:

    def test_unknown_ascii_token_raises(self):
        with pytest.raises(ParseError):
            parse("📜 🏠\n  NOPE\n  🛑")

    def test_unknown_emoji_raises(self):
        with pytest.raises(ParseError):
            parse("📜 🏠\n  🐉\n  🛑")

    def test_unknown_instruction_line_number(self):
        with pytest.raises(ParseError) as exc_info:
            parse("📜 🏠\n  📥 1\n  BADOP\n  🛑")
        assert exc_info.value.line_num == 3


# ---------------------------------------------------------------------------
# 10. Error: empty source raises ParseError
# ---------------------------------------------------------------------------

class TestErrorEmptySource:

    def test_empty_string_raises(self):
        with pytest.raises(ParseError):
            parse("")

    def test_only_newlines_raises(self):
        with pytest.raises(ParseError):
            parse("\n\n\n")

    def test_only_whitespace_raises(self):
        with pytest.raises(ParseError):
            parse("   \n   \n")

    def test_only_comments_raises(self):
        with pytest.raises(ParseError):
            parse("💭 just a comment\n💭 another comment\n")


# ---------------------------------------------------------------------------
# 11. Instruction.line_num is set correctly
# ---------------------------------------------------------------------------

class TestInstructionLineNum:

    def test_first_instruction_line_num(self):
        # Line 1: 📜 🏠, Line 2: 📥 99
        prog = parse("📜 🏠\n  📥 99\n  🛑")
        assert _instr(prog, 0).line_num == 2

    def test_second_instruction_line_num(self):
        prog = parse("📜 🏠\n  📥 1\n  📥 2\n  🛑")
        assert _instr(prog, 1).line_num == 3

    def test_line_num_skips_blanks_and_comments(self):
        # Line 1: 📜 🏠, Line 2: blank, Line 3: 💭 comment, Line 4: 📥 5
        source = "📜 🏠\n\n  💭 ignore\n  📥 5\n  🛑"
        prog = parse(source)
        assert _instr(prog, 0).line_num == 4

    def test_line_num_across_function_boundary(self):
        source = "📜 🏠\n  🛑\n📜 helper\n  📲"
        prog = parse(source)
        helper_instr = prog.functions["helper"].instructions[0]
        assert helper_instr.line_num == 4

    def test_halt_line_num(self):
        source = "📜 🏠\n  📥 1\n  📥 2\n  ➕\n  🛑"
        prog = parse(source)
        halt_instr = _instr(prog, 3)
        assert halt_instr.op == Op.HALT
        assert halt_instr.line_num == 5


# ---------------------------------------------------------------------------
# 12. Instruction.source is set to the stripped source line
# ---------------------------------------------------------------------------

class TestInstructionSource:

    def test_source_is_stripped(self):
        prog = parse("📜 🏠\n    📥 42\n  🛑")
        assert _instr(prog, 0).source == "📥 42"

    def test_source_matches_original_token_and_arg(self):
        prog = parse('📜 🏠\n  💬 "hi there"\n  🛑')
        assert _instr(prog, 0).source == '💬 "hi there"'

    def test_source_for_no_arg_instruction(self):
        prog = parse("📜 🏠\n  📋\n  🛑")
        # DUP has no argument
        assert _instr(prog, 0).source == "📋"

    def test_source_with_leading_trailing_spaces(self):
        prog = parse("📜 🏠\n\t  ➕  \n  🛑")
        assert _instr(prog, 0).source == "➕"

    def test_source_for_store_with_arg(self):
        prog = parse("📜 🏠\n  💾 🅰️\n  🛑")
        assert _instr(prog, 0).source == "💾 🅰️"


# ---------------------------------------------------------------------------
# 13. Variation selector variants: ✖️/✖ both parse to Op.MUL
# ---------------------------------------------------------------------------

class TestVariationSelectorMUL:

    def test_mul_with_variation_selector(self):
        prog = parse("📜 🏠\n  ✖️\n  🛑")
        assert _instr(prog, 0).op == Op.MUL

    def test_mul_without_variation_selector(self):
        prog = parse("📜 🏠\n  ✖\n  🛑")
        assert _instr(prog, 0).op == Op.MUL

    def test_both_mul_variants_equivalent(self):
        prog_vs = parse("📜 🏠\n  ✖️\n  🛑")
        prog_plain = parse("📜 🏠\n  ✖\n  🛑")
        assert _instr(prog_vs, 0).op == _instr(prog_plain, 0).op


# ---------------------------------------------------------------------------
# 14. Variation selector variants: 🖨️/🖨 both parse to Op.PRINTLN
# ---------------------------------------------------------------------------

class TestVariationSelectorPRINTLN:

    def test_println_with_variation_selector(self):
        prog = parse("📜 🏠\n  🖨️\n  🛑")
        assert _instr(prog, 0).op == Op.PRINTLN

    def test_println_without_variation_selector(self):
        prog = parse("📜 🏠\n  🖨\n  🛑")
        assert _instr(prog, 0).op == Op.PRINTLN

    def test_both_println_variants_equivalent(self):
        prog_vs = parse("📜 🏠\n  🖨️\n  🛑")
        prog_plain = parse("📜 🏠\n  🖨\n  🛑")
        assert _instr(prog_vs, 0).op == _instr(prog_plain, 0).op


# ---------------------------------------------------------------------------
# 15. Miscellaneous parser correctness
# ---------------------------------------------------------------------------

class TestMiscParser:

    def test_dup_has_no_arg(self):
        prog = parse("📜 🏠\n  📋\n  🛑")
        assert _instr(prog, 0).op == Op.DUP
        assert _instr(prog, 0).arg is None

    def test_store_arg_is_string(self):
        prog = parse("📜 🏠\n  💾 🔢\n  🛑")
        assert _instr(prog, 0).op == Op.STORE
        assert _instr(prog, 0).arg == "🔢"

    def test_prints_double_quote_string(self):
        prog = parse('📜 🏠\n  💬 "hello"\n  🛑')
        assert _instr(prog, 0).op == Op.PRINTS
        assert _instr(prog, 0).arg == "hello"

    def test_prints_single_quote_string(self):
        prog = parse("📜 🏠\n  💬 'world'\n  🛑")
        assert _instr(prog, 0).op == Op.PRINTS
        assert _instr(prog, 0).arg == "world"

    def test_program_type_is_program(self):
        from emojiasm.parser import Program
        prog = parse("📜 🏠\n  🛑")
        assert isinstance(prog, Program)

    def test_function_instructions_are_list_of_instruction(self):
        from emojiasm.parser import Instruction
        prog = parse("📜 🏠\n  📥 1\n  🛑")
        for instr in _func(prog).instructions:
            assert isinstance(instr, Instruction)

    def test_function_labels_dict_is_empty_when_no_labels(self):
        prog = parse("📜 🏠\n  📥 1\n  🛑")
        assert _func(prog).labels == {}

    def test_instruction_count_matches_source_lines(self):
        source = "📜 🏠\n  📥 1\n  📥 2\n  ➕\n  🖨️\n  🛑"
        prog = parse(source)
        assert len(_func(prog).instructions) == 5

    def test_jmp_arg_is_label_name_string(self):
        prog = parse("📜 🏠\n  👉 🏁\n🏷️ 🏁\n  🛑")
        assert _instr(prog, 0).op == Op.JMP
        assert _instr(prog, 0).arg == "🏁"

    def test_call_arg_is_function_name_string(self):
        prog = parse("📜 🏠\n  📞 helper\n  🛑\n📜 helper\n  📲")
        assert _instr(prog, 0).op == Op.CALL
        assert _instr(prog, 0).arg == "helper"

    def test_no_function_directive_auto_creates_home(self):
        """Instructions without a preceding 📜 auto-assign to an implicit 🏠."""
        prog = parse("📥 1\n🛑")
        assert "🏠" in prog.functions
        assert prog.entry_point == "🏠"
