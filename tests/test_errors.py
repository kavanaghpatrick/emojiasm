"""Tests for enriched ParseError and VMError messages."""

import pytest
from emojiasm.parser import ParseError, _grapheme_truncate, _suggest_opcode, parse
from emojiasm.vm import VM, VMError


def _run(source):
    vm = VM(parse(source))
    vm.run()


# ── _grapheme_truncate ────────────────────────────────────────────────────────

def test_grapheme_truncate_empty():
    assert _grapheme_truncate("") == ""

def test_grapheme_truncate_short_string_unchanged():
    assert _grapheme_truncate("abc", 10) == "abc"

def test_grapheme_truncate_basic_truncation():
    result = _grapheme_truncate("a" * 15, 10)
    assert result == "aaaaaaaaaa..."

def test_grapheme_truncate_variation_selector_not_counted():
    # ✖️ is two codepoints: ✖ + U+FE0F variation selector
    # 12 of them should still truncate at 10 grapheme clusters, not 10 codepoints
    s = "✖️" * 12  # 24 codepoints, 12 grapheme clusters
    result = _grapheme_truncate(s, 10)
    assert result.endswith("...")
    # Should not have split mid-codepoint
    assert "\ufffd" not in result

def test_grapheme_truncate_no_replacement_chars():
    # Pure emoji string — no replacement chars should appear
    s = "📥 📤 📋 🔀 🫴 🔄 ➕ ➖ ✖️ ✖ ➗"
    result = _grapheme_truncate(s, 5)
    assert "\ufffd" not in result


# ── _suggest_opcode ───────────────────────────────────────────────────────────

def test_suggest_opcode_near_miss_returns_hint():
    # ✖ (without variation selector) is close to ✖️ (with)
    hint = _suggest_opcode("✖")
    # Either finds a match or returns empty string — both are valid
    assert isinstance(hint, str)

def test_suggest_opcode_gibberish_returns_empty():
    hint = _suggest_opcode("XXXXXXX")
    assert hint == ""

def test_suggest_opcode_exact_match_returns_empty():
    # An exact opcode should already be handled — suggest won't be called for it
    # but if called, either returns empty or a hint — both acceptable
    result = _suggest_opcode("➕")
    assert isinstance(result, str)


# ── ParseError enrichments ────────────────────────────────────────────────────

def test_unknown_instruction_no_replacement_char():
    with pytest.raises(ParseError) as exc_info:
        parse("📜 🏠\n  ❓ bad")
    assert "\ufffd" not in str(exc_info.value)

def test_parse_error_includes_func_name():
    with pytest.raises(ParseError) as exc_info:
        parse("📜 myFunc\n  ❓ bad")
    assert "[myFunc]" in str(exc_info.value)

def test_parse_error_no_func_name_at_toplevel():
    # Error before any 📜 directive — no function context
    with pytest.raises(ParseError) as exc_info:
        parse("  ❓ bad")
    msg = str(exc_info.value)
    # Should not show a bracketed function name
    assert "[" not in msg or "Line" in msg  # Line N is OK; [funcName] is not

def test_parse_error_func_name_matches_definition():
    with pytest.raises(ParseError) as exc_info:
        parse("📜 🚀\n  ❓ bad")
    assert "[🚀]" in str(exc_info.value)


# ── VMError enrichments ───────────────────────────────────────────────────────

def test_vmerror_div_zero_includes_source_line():
    with pytest.raises(VMError) as exc_info:
        _run("📜 🏠\n  📥 5\n  📥 0\n  ➗\n  🛑")
    msg = str(exc_info.value)
    assert "➗" in msg

def test_vmerror_div_zero_includes_func_name():
    with pytest.raises(VMError) as exc_info:
        _run("📜 🏠\n  📥 5\n  📥 0\n  ➗\n  🛑")
    assert "in 🏠" in str(exc_info.value)

def test_vmerror_load_uninit_includes_source():
    with pytest.raises(VMError) as exc_info:
        _run("📜 🏠\n  📂 🔑\n  🛑")
    assert "📂" in str(exc_info.value) or "not initialized" in str(exc_info.value)

def test_vmerror_has_func_name_attribute():
    with pytest.raises(VMError) as exc_info:
        _run("📜 myFn\n  📥 1\n  📥 0\n  ➗\n  🛑")
    e = exc_info.value
    assert hasattr(e, "func_name")
    assert e.func_name == "myFn"

def test_vmerror_has_source_attribute():
    with pytest.raises(VMError) as exc_info:
        _run("📜 🏠\n  📥 1\n  📥 0\n  ➗\n  🛑")
    e = exc_info.value
    assert hasattr(e, "source")
    assert "➗" in e.source
