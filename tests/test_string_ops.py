"""Tests for string operations: STRLEN, SUBSTR, STRINDEX, STR2NUM, NUM2STR."""

import pytest
from emojiasm.parser import parse
from emojiasm.vm import VM, VMError


def run(source: str, max_steps: int = 10000) -> list[str]:
    program = parse(source)
    vm = VM(program)
    vm.max_steps = max_steps
    return vm.run()


# ── STRLEN ──────────────────────────────────────────────────────────────


class TestStrlen:
    def test_empty_string(self):
        out = run('📜 🏠\n  💬 ""\n  🧵\n  🖨️\n  🛑')
        assert "".join(out).strip() == "0"

    def test_hello(self):
        out = run('📜 🏠\n  💬 "hello"\n  🧵\n  🖨️\n  🛑')
        assert "".join(out).strip() == "5"

    def test_single_char(self):
        out = run('📜 🏠\n  💬 "x"\n  🧵\n  🖨️\n  🛑')
        assert "".join(out).strip() == "1"

    def test_string_with_spaces(self):
        out = run('📜 🏠\n  💬 "a b c"\n  🧵\n  🖨️\n  🛑')
        assert "".join(out).strip() == "5"

    def test_type_error(self):
        with pytest.raises(VMError, match="STRLEN requires a string"):
            run("📜 🏠\n  📥 42\n  🧵\n  🛑")


# ── SUBSTR ──────────────────────────────────────────────────────────────


class TestSubstr:
    def test_basic(self):
        # "hello"[1:1+3] == "ell"
        out = run('📜 🏠\n  💬 "hello"\n  📥 1\n  📥 3\n  ✂️\n  🖨️\n  🛑')
        assert "".join(out).strip() == "ell"

    def test_from_start(self):
        # "abcde"[0:0+2] == "ab"
        out = run('📜 🏠\n  💬 "abcde"\n  📥 0\n  📥 2\n  ✂️\n  🖨️\n  🛑')
        assert "".join(out).strip() == "ab"

    def test_negative_start(self):
        # "hello"[-3:-3+2] == "ll"
        out = run('📜 🏠\n  💬 "hello"\n  📥 -3\n  📥 2\n  ✂️\n  🖨️\n  🛑')
        assert "".join(out).strip() == "ll"

    def test_zero_length(self):
        # "hello"[2:2+0] == ""
        out = run('📜 🏠\n  💬 "hello"\n  📥 2\n  📥 0\n  ✂️\n  🧵\n  🖨️\n  🛑')
        assert "".join(out).strip() == "0"

    def test_full_string(self):
        # "abc"[0:0+3] == "abc"
        out = run('📜 🏠\n  💬 "abc"\n  📥 0\n  📥 3\n  ✂️\n  🖨️\n  🛑')
        assert "".join(out).strip() == "abc"

    def test_type_error(self):
        with pytest.raises(VMError, match="SUBSTR requires a string"):
            run("📜 🏠\n  📥 42\n  📥 0\n  📥 1\n  ✂️\n  🛑")

    def test_no_variation_selector(self):
        """SUBSTR also works with bare scissors emoji (no variation selector)."""
        out = run('📜 🏠\n  💬 "hello"\n  📥 0\n  📥 2\n  ✂\n  🖨️\n  🛑')
        assert "".join(out).strip() == "he"


# ── STRINDEX ────────────────────────────────────────────────────────────


class TestStrindex:
    def test_found(self):
        out = run('📜 🏠\n  💬 "hello world"\n  💬 "world"\n  🔍\n  🖨️\n  🛑')
        assert "".join(out).strip() == "6"

    def test_found_at_start(self):
        out = run('📜 🏠\n  💬 "abc"\n  💬 "a"\n  🔍\n  🖨️\n  🛑')
        assert "".join(out).strip() == "0"

    def test_not_found(self):
        out = run('📜 🏠\n  💬 "hello"\n  💬 "xyz"\n  🔍\n  🖨️\n  🛑')
        assert "".join(out).strip() == "-1"

    def test_empty_substring(self):
        out = run('📜 🏠\n  💬 "hello"\n  💬 ""\n  🔍\n  🖨️\n  🛑')
        assert "".join(out).strip() == "0"


# ── STR2NUM ─────────────────────────────────────────────────────────────


class TestStr2Num:
    def test_integer(self):
        out = run('📜 🏠\n  💬 "42"\n  🔁\n  🖨️\n  🛑')
        assert "".join(out).strip() == "42"

    def test_negative_integer(self):
        out = run('📜 🏠\n  💬 "-7"\n  🔁\n  🖨️\n  🛑')
        assert "".join(out).strip() == "-7"

    def test_float(self):
        out = run('📜 🏠\n  💬 "3.14"\n  🔁\n  🖨️\n  🛑')
        assert "".join(out).strip() == "3.14"

    def test_invalid_raises_error(self):
        with pytest.raises(VMError, match="STR2NUM: cannot parse"):
            run('📜 🏠\n  💬 "abc"\n  🔁\n  🛑')

    def test_type_error(self):
        with pytest.raises(VMError, match="STR2NUM requires a string"):
            run("📜 🏠\n  📥 42\n  🔁\n  🛑")

    def test_arithmetic_after_parse(self):
        """Parse a string to number, then use it in arithmetic."""
        out = run('📜 🏠\n  💬 "10"\n  🔁\n  📥 5\n  ➕\n  🖨️\n  🛑')
        assert "".join(out).strip() == "15"


# ── NUM2STR ─────────────────────────────────────────────────────────────


class TestNum2Str:
    def test_integer(self):
        out = run("📜 🏠\n  📥 42\n  🔤\n  🖨️\n  🛑")
        assert "".join(out).strip() == "42"

    def test_negative(self):
        out = run("📜 🏠\n  📥 -5\n  🔤\n  🖨️\n  🛑")
        assert "".join(out).strip() == "-5"

    def test_float(self):
        out = run("📜 🏠\n  📥 3.14\n  🔤\n  🖨️\n  🛑")
        assert "".join(out).strip() == "3.14"

    def test_is_string_type(self):
        """NUM2STR result should be a string usable with STRLEN."""
        out = run("📜 🏠\n  📥 123\n  🔤\n  🧵\n  🖨️\n  🛑")
        assert "".join(out).strip() == "3"

    def test_concat_after_convert(self):
        """NUM2STR result can be concatenated with other strings."""
        out = run('📜 🏠\n  💬 "val="\n  📥 42\n  🔤\n  ➕\n  🖨️\n  🛑')
        assert "".join(out).strip() == "val=42"


# ── Integration / end-to-end ────────────────────────────────────────────


class TestStringOpsIntegration:
    def test_strlen_substr_chain(self):
        """Get length of string, use it to extract full substring."""
        src = '\n'.join([
            '📜 🏠',
            '  💬 "hello"',
            '  📋',           # DUP the string
            '  🧵',           # STRLEN -> 5
            '  💾 🅰️',       # store length
            '  📥 0',         # start=0
            '  📂 🅰️',       # load length
            '  ✂️',           # SUBSTR -> "hello"
            '  🖨️',
            '  🛑',
        ])
        out = run(src)
        assert "".join(out).strip() == "hello"

    def test_strindex_then_substr(self):
        """Find a substring, then extract from that position."""
        src = '\n'.join([
            '📜 🏠',
            '  💬 "hello world"',
            '  📋',                # DUP
            '  💬 "world"',
            '  🔍',                # STRINDEX -> 6
            '  📥 5',              # length of "world"
            '  ✂️',                # SUBSTR from index 6, length 5
            '  🖨️',
            '  🛑',
        ])
        out = run(src)
        assert "".join(out).strip() == "world"

    def test_num_to_str_to_num_roundtrip(self):
        """Convert number to string and back."""
        src = '\n'.join([
            '📜 🏠',
            '  📥 42',
            '  🔤',       # NUM2STR -> "42"
            '  🔁',       # STR2NUM -> 42
            '  📥 8',
            '  ➕',       # 42 + 8 = 50
            '  🖨️',
            '  🛑',
        ])
        out = run(src)
        assert "".join(out).strip() == "50"

    def test_all_five_ops(self):
        """Program using all 5 string ops together."""
        src = '\n'.join([
            '📜 🏠',
            '  💬 "The answer is 42"',   # push string
            '  📋',                        # DUP for later use
            '  🧵',                        # STRLEN -> 17
            '  🖨️',                       # print 17
            '  💬 "answer"',
            '  🔍',                        # STRINDEX -> 4
            '  🖨️',                       # print 4
            '  📥 100',
            '  🔤',                        # NUM2STR -> "100"
            '  🖨️',                       # print "100"
            '  💬 "55"',
            '  🔁',                        # STR2NUM -> 55
            '  🖨️',                       # print 55
            '  💬 "abcdef"',
            '  📥 2',
            '  📥 3',
            '  ✂️',                        # SUBSTR -> "cde"
            '  🖨️',                       # print "cde"
            '  🛑',
        ])
        out = run(src)
        result = "".join(out)
        assert "16" in result
        assert "4" in result
        assert "100" in result
        assert "55" in result
        assert "cde" in result
