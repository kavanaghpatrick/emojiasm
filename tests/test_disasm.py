"""Tests for the EmojiASM disassembler."""

import pytest
from emojiasm.parser import parse
from emojiasm.disasm import disassemble


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _disasm(source: str) -> str:
    """Parse source and disassemble, returning the output string."""
    return disassemble(parse(source))


# ---------------------------------------------------------------------------
# 1. Simple program → output contains the function emoji name
# ---------------------------------------------------------------------------

class TestFunctionName:

    def test_home_function_name_appears(self):
        out = _disasm("📜 🏠\n  🛑")
        assert "🏠" in out

    def test_named_function_name_appears(self):
        out = _disasm("📜 fibonacci\n  📲")
        assert "fibonacci" in out

    def test_emoji_function_name_appears(self):
        out = _disasm("📜 🔽\n  📲")
        assert "🔽" in out

    def test_function_marker_emoji_appears(self):
        # The disassembler prefixes each function with 📜
        out = _disasm("📜 🏠\n  🛑")
        assert "📜" in out


# ---------------------------------------------------------------------------
# 2. PUSH → output contains 📥 and the value
# ---------------------------------------------------------------------------

class TestDisasmPush:

    def test_push_integer_contains_emoji(self):
        out = _disasm("📜 🏠\n  📥 42\n  🛑")
        assert "📥" in out

    def test_push_integer_contains_value(self):
        out = _disasm("📜 🏠\n  📥 42\n  🛑")
        assert "42" in out

    def test_push_negative_contains_value(self):
        out = _disasm("📜 🏠\n  📥 -7\n  🛑")
        assert "-7" in out

    def test_push_float_contains_value(self):
        out = _disasm("📜 🏠\n  📥 3.14\n  🛑")
        assert "3.14" in out

    def test_push_string_contains_emoji_and_value(self):
        out = _disasm('📜 🏠\n  📥 "hello"\n  🛑')
        assert "📥" in out
        assert "hello" in out

    def test_push_zero_contains_zero(self):
        out = _disasm("📜 🏠\n  📥 0\n  🛑")
        assert "📥" in out
        assert "0" in out


# ---------------------------------------------------------------------------
# 3. PRINTLN → output contains 🖨 or 🖨️
# ---------------------------------------------------------------------------

class TestDisasmPrintln:

    def test_println_emoji_present(self):
        out = _disasm("📜 🏠\n  🖨️\n  🛑")
        # OP_TO_EMOJI maps PRINTLN to one of the two variants; either is acceptable
        assert ("🖨" in out) or ("🖨️" in out)

    def test_println_from_plain_variant(self):
        out = _disasm("📜 🏠\n  🖨\n  🛑")
        assert ("🖨" in out) or ("🖨️" in out)


# ---------------------------------------------------------------------------
# 4. Label → output contains 🏷 and the label name
# ---------------------------------------------------------------------------

class TestDisasmLabel:

    def test_label_tag_emoji_appears(self):
        out = _disasm("📜 🏠\n🏷️ loop\n  🛑")
        # Disassembler emits 🏷️; a substring search for 🏷 matches both variants
        assert "🏷" in out

    def test_label_name_appears(self):
        out = _disasm("📜 🏠\n🏷️ loop\n  🛑")
        assert "loop" in out

    def test_emoji_label_name_appears(self):
        out = _disasm("📜 🏠\n🏷️ 🔁\n  🛑")
        assert "🔁" in out

    def test_label_at_mid_function_appears(self):
        source = "📜 🏠\n  📥 1\n🏷️ mid\n  📥 2\n  🛑"
        out = _disasm(source)
        assert "mid" in out


# ---------------------------------------------------------------------------
# 5. Multiple functions → output contains both function names
# ---------------------------------------------------------------------------

class TestDisasmMultipleFunctions:

    def test_both_function_names_present(self):
        source = "📜 🏠\n  📞 helper\n  🛑\n📜 helper\n  📲"
        out = _disasm(source)
        assert "🏠" in out
        assert "helper" in out

    def test_three_functions_all_present(self):
        source = "📜 🏠\n  🛑\n📜 alpha\n  📲\n📜 beta\n  📲"
        out = _disasm(source)
        assert "🏠" in out
        assert "alpha" in out
        assert "beta" in out

    def test_output_lists_functions_in_order(self):
        source = "📜 🏠\n  🛑\n📜 second\n  📲"
        out = _disasm(source)
        assert out.index("🏠") < out.index("second")


# ---------------------------------------------------------------------------
# 6. CALL → output contains 📞 and the callee name
# ---------------------------------------------------------------------------

class TestDisasmCall:

    def test_call_emoji_present(self):
        source = "📜 🏠\n  📞 helper\n  🛑\n📜 helper\n  📲"
        out = _disasm(source)
        assert "📞" in out

    def test_call_callee_name_present(self):
        source = "📜 🏠\n  📞 helper\n  🛑\n📜 helper\n  📲"
        out = _disasm(source)
        assert "helper" in out

    def test_call_emoji_function_callee(self):
        source = "📜 🏠\n  📞 🔲\n  🛑\n📜 🔲\n  📲"
        out = _disasm(source)
        assert "📞" in out
        assert "🔲" in out


# ---------------------------------------------------------------------------
# 7. STORE/LOAD → output contains 💾/📂 and the cell name
# ---------------------------------------------------------------------------

class TestDisasmStoreLoad:

    def test_store_emoji_present(self):
        out = _disasm("📜 🏠\n  📥 5\n  💾 myVar\n  🛑")
        assert "💾" in out

    def test_store_cell_name_present(self):
        out = _disasm("📜 🏠\n  📥 5\n  💾 myVar\n  🛑")
        assert "myVar" in out

    def test_load_emoji_present(self):
        out = _disasm("📜 🏠\n  📂 myVar\n  🛑")
        assert "📂" in out

    def test_load_cell_name_present(self):
        out = _disasm("📜 🏠\n  📂 myVar\n  🛑")
        assert "myVar" in out

    def test_store_and_load_emoji_cell_names(self):
        source = "📜 🏠\n  📥 1\n  💾 🅰️\n  📂 🅰️\n  🛑"
        out = _disasm(source)
        assert "💾" in out
        assert "📂" in out
        assert "🅰️" in out


# ---------------------------------------------------------------------------
# 8. PRINTS → output contains 💬 and the string literal
# ---------------------------------------------------------------------------

class TestDisasmPrints:

    def test_prints_emoji_present(self):
        out = _disasm('📜 🏠\n  💬 "hello world"\n  🛑')
        assert "💬" in out

    def test_prints_string_value_present(self):
        out = _disasm('📜 🏠\n  💬 "hello world"\n  🛑')
        assert "hello world" in out

    def test_prints_string_is_quoted_in_output(self):
        out = _disasm('📜 🏠\n  💬 "greetings"\n  🛑')
        assert '"greetings"' in out

    def test_prints_empty_string(self):
        out = _disasm('📜 🏠\n  💬 ""\n  🛑')
        assert "💬" in out
        assert '""' in out

    def test_prints_newline_escape(self):
        out = _disasm('📜 🏠\n  💬 "\\n"\n  🛑')
        assert "💬" in out


# ---------------------------------------------------------------------------
# 9. Round-trip property: all opcodes from source appear in disassembly output
# ---------------------------------------------------------------------------

class TestRoundTrip:

    def test_all_opcodes_in_output(self):
        source = (
            "📜 🏠\n"
            "  📥 10\n"
            "  💾 x\n"
            "  📂 x\n"
            "  📋\n"
            "  ➕\n"
            "  🖨️\n"
            "  🛑\n"
        )
        out = _disasm(source)
        assert "📥" in out   # PUSH
        assert "💾" in out   # STORE
        assert "📂" in out   # LOAD
        assert "📋" in out   # DUP
        assert "➕" in out   # ADD
        # PRINTLN → one of its two variants
        assert ("🖨" in out) or ("🖨️" in out)
        assert "🛑" in out   # HALT

    def test_roundtrip_control_flow(self):
        source = (
            "📜 🏠\n"
            "  📥 0\n"
            "🏷️ top\n"
            "  📥 1\n"
            "  ➕\n"
            "  📋\n"
            "  📥 5\n"
            "  🟰\n"
            "  😤 top\n"
            "  🛑\n"
        )
        out = _disasm(source)
        assert "📥" in out
        assert "➕" in out
        assert "📋" in out
        assert "🟰" in out
        assert "😤" in out
        assert "top" in out
        assert "🛑" in out

    def test_roundtrip_function_call(self):
        source = (
            "📜 🏠\n"
            "  📥 3\n"
            "  📞 double\n"
            "  🛑\n"
            "📜 double\n"
            "  📥 2\n"
            "  ✖️\n"
            "  📲\n"
        )
        out = _disasm(source)
        assert "📥" in out
        assert "📞" in out
        assert "double" in out
        assert "📲" in out


# ---------------------------------------------------------------------------
# 10. Disassembly output is a non-empty string
# ---------------------------------------------------------------------------

class TestOutputIsNonEmptyString:

    def test_output_is_str(self):
        out = _disasm("📜 🏠\n  🛑")
        assert isinstance(out, str)

    def test_output_is_non_empty(self):
        out = _disasm("📜 🏠\n  🛑")
        assert len(out) > 0

    def test_output_has_content_beyond_whitespace(self):
        out = _disasm("📜 🏠\n  🛑")
        assert out.strip() != ""

    def test_output_for_complex_program_is_long(self):
        source = (
            "📜 🏠\n"
            "  📥 1\n  📥 2\n  ➕\n  🖨️\n"
            "  📥 3\n  📥 4\n  ✖️\n  🖨️\n"
            "  🛑\n"
        )
        out = _disasm(source)
        assert len(out) > 20


# ---------------------------------------------------------------------------
# 11. JMP / JZ / JNZ disassembly includes the label name
# ---------------------------------------------------------------------------

class TestDisasmJumps:

    def test_jmp_emoji_present(self):
        out = _disasm("📜 🏠\n  👉 🏁\n🏷️ 🏁\n  🛑")
        assert "👉" in out

    def test_jmp_label_name_present(self):
        out = _disasm("📜 🏠\n  👉 🏁\n🏷️ 🏁\n  🛑")
        assert "🏁" in out

    def test_jz_emoji_present(self):
        out = _disasm("📜 🏠\n  📥 0\n  🤔 end\n🏷️ end\n  🛑")
        assert "🤔" in out

    def test_jz_label_name_present(self):
        out = _disasm("📜 🏠\n  📥 0\n  🤔 end\n🏷️ end\n  🛑")
        assert "end" in out

    def test_jnz_emoji_present(self):
        out = _disasm("📜 🏠\n  📥 1\n  😤 loop\n🏷️ loop\n  🛑")
        assert "😤" in out

    def test_jnz_label_name_present(self):
        out = _disasm("📜 🏠\n  📥 1\n  😤 loop\n🏷️ loop\n  🛑")
        assert "loop" in out

    def test_jmp_emoji_label_name_present(self):
        out = _disasm("📜 🏠\n  👉 🔁\n🏷️ 🔁\n  🛑")
        assert "👉" in out
        assert "🔁" in out


# ---------------------------------------------------------------------------
# 12. HALT appears in disassembly
# ---------------------------------------------------------------------------

class TestDisasmHalt:

    def test_halt_emoji_present(self):
        out = _disasm("📜 🏠\n  🛑")
        assert "🛑" in out

    def test_halt_after_instructions(self):
        out = _disasm("📜 🏠\n  📥 1\n  📥 2\n  ➕\n  🛑")
        assert "🛑" in out

    def test_halt_is_distinct_from_other_ops(self):
        out = _disasm("📜 🏠\n  🛑")
        # Output should not contain spurious unrelated ops
        assert "📥" not in out


# ---------------------------------------------------------------------------
# 13. Fibonacci example file
# ---------------------------------------------------------------------------

class TestFibonacciExample:

    @pytest.fixture
    def fibonacci_source(self):
        import os
        path = os.path.join(
            os.path.dirname(__file__), "..", "examples", "fibonacci.emoji"
        )
        with open(os.path.abspath(path), encoding="utf-8") as f:
            return f.read()

    def test_fibonacci_disassembles_without_error(self, fibonacci_source):
        out = disassemble(parse(fibonacci_source))
        assert isinstance(out, str)
        assert len(out) > 0

    def test_fibonacci_output_contains_function_name(self, fibonacci_source):
        out = disassemble(parse(fibonacci_source))
        assert "🏠" in out

    def test_fibonacci_output_contains_push(self, fibonacci_source):
        # fibonacci.emoji uses 📥 for several pushes
        out = disassemble(parse(fibonacci_source))
        assert "📥" in out

    def test_fibonacci_output_contains_store(self, fibonacci_source):
        # fibonacci.emoji uses 💾 to store variables
        out = disassemble(parse(fibonacci_source))
        assert "💾" in out

    def test_fibonacci_output_contains_load(self, fibonacci_source):
        # fibonacci.emoji uses 📂 to load variables
        out = disassemble(parse(fibonacci_source))
        assert "📂" in out

    def test_fibonacci_output_contains_add(self, fibonacci_source):
        # fibonacci.emoji uses ➕ to compute next value
        out = disassemble(parse(fibonacci_source))
        assert "➕" in out

    def test_fibonacci_output_contains_jnz(self, fibonacci_source):
        # fibonacci.emoji uses 😤 (JNZ) for the loop-exit guard
        out = disassemble(parse(fibonacci_source))
        assert "😤" in out

    def test_fibonacci_output_contains_jmp(self, fibonacci_source):
        # fibonacci.emoji uses 👉 (JMP) to loop back
        out = disassemble(parse(fibonacci_source))
        assert "👉" in out

    def test_fibonacci_output_contains_halt(self, fibonacci_source):
        out = disassemble(parse(fibonacci_source))
        assert "🛑" in out

    def test_fibonacci_output_contains_prints(self, fibonacci_source):
        # fibonacci.emoji uses 💬 for string literals
        out = disassemble(parse(fibonacci_source))
        assert "💬" in out

    def test_fibonacci_output_contains_loop_label(self, fibonacci_source):
        # fibonacci.emoji defines a 🔁 label
        out = disassemble(parse(fibonacci_source))
        assert "🔁" in out

    def test_fibonacci_output_contains_done_label(self, fibonacci_source):
        # fibonacci.emoji defines a 🏁 label
        out = disassemble(parse(fibonacci_source))
        assert "🏁" in out

    def test_fibonacci_output_contains_variable_names(self, fibonacci_source):
        # fibonacci.emoji stores to 🅰️, 🅱️, 🔢, 🌡️
        out = disassemble(parse(fibonacci_source))
        assert "🅰️" in out
        assert "🅱️" in out

    def test_fibonacci_output_contains_print(self, fibonacci_source):
        # fibonacci.emoji uses 📢 (PRINT) to print values
        out = disassemble(parse(fibonacci_source))
        assert "📢" in out
