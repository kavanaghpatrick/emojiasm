"""Tests for the module/import system (📦 directive)."""

import os
import textwrap
import tempfile

import pytest

from emojiasm.parser import parse, ParseError
from emojiasm.vm import VM
from emojiasm.opcodes import Op


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: str, content: str) -> None:
    """Write *content* to *path*, creating parent dirs as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(content))


def _run(source: str, base_path: str = "", max_steps: int = 10000) -> list[str]:
    """Parse + execute source, returning captured output lines."""
    program = parse(source, base_path=base_path)
    vm = VM(program)
    vm.max_steps = max_steps
    return vm.run()


# ---------------------------------------------------------------------------
# 1. Basic import: merge imported functions
# ---------------------------------------------------------------------------

class TestBasicImport:

    def test_import_adds_function_from_lib(self, tmp_path):
        lib = tmp_path / "mylib.emoji"
        lib.write_text(
            "📜 🔲\n  📋\n  ✖️\n  📲\n",
            encoding="utf-8",
        )
        source = "📦 mylib\n📜 🏠\n  📥 6\n  📞 🔲\n  🖨️\n  🛑"
        prog = parse(source, base_path=str(tmp_path))
        assert "🔲" in prog.functions
        assert "🏠" in prog.functions

    def test_import_function_is_callable(self, tmp_path):
        lib = tmp_path / "mylib.emoji"
        lib.write_text(
            "📜 🔲\n  📋\n  ✖️\n  📲\n",
            encoding="utf-8",
        )
        source = "📦 mylib\n📜 🏠\n  📥 6\n  📞 🔲\n  🖨️\n  🛑"
        out = _run(source, base_path=str(tmp_path))
        assert "".join(out).strip() == "36"

    def test_import_multiple_functions(self, tmp_path):
        lib = tmp_path / "utils.emoji"
        lib.write_text(
            "📜 🔲\n  📋\n  ✖️\n  📲\n"
            "📜 🔁\n  📋\n  ➕\n  📲\n",
            encoding="utf-8",
        )
        source = "📦 utils\n📜 🏠\n  📥 5\n  📞 🔁\n  🖨️\n  🛑"
        out = _run(source, base_path=str(tmp_path))
        assert "".join(out).strip() == "10"

    def test_import_preserves_local_functions(self, tmp_path):
        lib = tmp_path / "lib.emoji"
        lib.write_text("📜 helper\n  📥 99\n  📲\n", encoding="utf-8")
        source = (
            "📦 lib\n"
            "📜 🏠\n  📞 local_fn\n  🖨️\n  🛑\n"
            "📜 local_fn\n  📥 42\n  📲\n"
        )
        out = _run(source, base_path=str(tmp_path))
        assert "".join(out).strip() == "42"


# ---------------------------------------------------------------------------
# 2. Circular import detection
# ---------------------------------------------------------------------------

class TestCircularImport:

    def test_direct_circular_import_raises(self, tmp_path):
        a = tmp_path / "a.emoji"
        b = tmp_path / "b.emoji"
        a.write_text("📦 b\n📜 🏠\n  🛑\n", encoding="utf-8")
        b.write_text("📦 a\n📜 helper\n  📲\n", encoding="utf-8")

        with open(a, "r", encoding="utf-8") as f:
            source = f.read()
        seen = {str(a)}
        with pytest.raises(ParseError, match="[Cc]ircular"):
            parse(source, base_path=str(tmp_path), _seen_files=seen)

    def test_self_import_raises(self, tmp_path):
        me = tmp_path / "me.emoji"
        me.write_text("📦 me\n📜 🏠\n  🛑\n", encoding="utf-8")

        with open(me, "r", encoding="utf-8") as f:
            source = f.read()
        seen = {str(me)}
        with pytest.raises(ParseError, match="[Cc]ircular"):
            parse(source, base_path=str(tmp_path), _seen_files=seen)

    def test_indirect_circular_import_raises(self, tmp_path):
        """A -> B -> C -> A should raise."""
        (tmp_path / "a.emoji").write_text("📦 b\n📜 🏠\n  🛑\n", encoding="utf-8")
        (tmp_path / "b.emoji").write_text("📦 c\n📜 bfn\n  📲\n", encoding="utf-8")
        (tmp_path / "c.emoji").write_text("📦 a\n📜 cfn\n  📲\n", encoding="utf-8")

        with open(tmp_path / "a.emoji", "r", encoding="utf-8") as f:
            source = f.read()
        seen = {str(tmp_path / "a.emoji")}
        with pytest.raises(ParseError, match="[Cc]ircular"):
            parse(source, base_path=str(tmp_path), _seen_files=seen)


# ---------------------------------------------------------------------------
# 3. File not found
# ---------------------------------------------------------------------------

class TestImportNotFound:

    def test_missing_module_raises(self, tmp_path):
        source = "📦 nonexistent\n📜 🏠\n  🛑"
        with pytest.raises(ParseError, match="Cannot find module"):
            parse(source, base_path=str(tmp_path))

    def test_missing_module_message_contains_name(self, tmp_path):
        source = "📦 missing_lib\n📜 🏠\n  🛑"
        with pytest.raises(ParseError, match="missing_lib"):
            parse(source, base_path=str(tmp_path))


# ---------------------------------------------------------------------------
# 4. Transitive imports: A imports B, B imports C
# ---------------------------------------------------------------------------

class TestTransitiveImport:

    def test_transitive_import_merges_all_functions(self, tmp_path):
        (tmp_path / "c.emoji").write_text(
            "📜 cfn\n  📥 100\n  📲\n",
            encoding="utf-8",
        )
        (tmp_path / "b.emoji").write_text(
            "📦 c\n📜 bfn\n  📞 cfn\n  📥 1\n  ➕\n  📲\n",
            encoding="utf-8",
        )
        source = "📦 b\n📜 🏠\n  📞 bfn\n  🖨️\n  🛑"
        prog = parse(source, base_path=str(tmp_path))
        assert "cfn" in prog.functions
        assert "bfn" in prog.functions
        assert "🏠" in prog.functions

    def test_transitive_import_executes_correctly(self, tmp_path):
        (tmp_path / "c.emoji").write_text(
            "📜 cfn\n  📥 100\n  📲\n",
            encoding="utf-8",
        )
        (tmp_path / "b.emoji").write_text(
            "📦 c\n📜 bfn\n  📞 cfn\n  📥 1\n  ➕\n  📲\n",
            encoding="utf-8",
        )
        source = "📦 b\n📜 🏠\n  📞 bfn\n  🖨️\n  🛑"
        out = _run(source, base_path=str(tmp_path))
        assert "".join(out).strip() == "101"


# ---------------------------------------------------------------------------
# 5. Duplicate function names: last-wins
# ---------------------------------------------------------------------------

class TestDuplicateFunction:

    def test_local_overrides_imported(self, tmp_path):
        lib = tmp_path / "lib.emoji"
        lib.write_text("📜 🔲\n  📥 999\n  📲\n", encoding="utf-8")
        # Local 🔲 should win because it is defined after the import
        source = "📦 lib\n📜 🔲\n  📥 42\n  📲\n📜 🏠\n  📞 🔲\n  🖨️\n  🛑"
        out = _run(source, base_path=str(tmp_path))
        assert "".join(out).strip() == "42"

    def test_imported_overrides_earlier_local(self, tmp_path):
        lib = tmp_path / "lib.emoji"
        lib.write_text("📜 🔲\n  📥 999\n  📲\n", encoding="utf-8")
        # Import comes AFTER local definition, so imported version wins
        source = "📜 🔲\n  📥 42\n  📲\n📦 lib\n📜 🏠\n  📞 🔲\n  🖨️\n  🛑"
        out = _run(source, base_path=str(tmp_path))
        assert "".join(out).strip() == "999"


# ---------------------------------------------------------------------------
# 6. EMOJIASM_PATH environment variable
# ---------------------------------------------------------------------------

class TestEmojiAsmPath:

    def test_import_from_env_path(self, tmp_path, monkeypatch):
        lib_dir = tmp_path / "libs"
        lib_dir.mkdir()
        (lib_dir / "remote_lib.emoji").write_text(
            "📜 remote_fn\n  📥 77\n  📲\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("EMOJIASM_PATH", str(lib_dir))
        # base_path is a different directory with no remote_lib.emoji
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        source = "📦 remote_lib\n📜 🏠\n  📞 remote_fn\n  🖨️\n  🛑"
        out = _run(source, base_path=str(src_dir))
        assert "".join(out).strip() == "77"

    def test_base_path_takes_priority_over_env(self, tmp_path, monkeypatch):
        """If the module exists in both base_path and EMOJIASM_PATH, base_path wins."""
        lib_dir = tmp_path / "libs"
        lib_dir.mkdir()
        (lib_dir / "mod.emoji").write_text(
            "📜 fn\n  📥 1\n  📲\n", encoding="utf-8",
        )
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "mod.emoji").write_text(
            "📜 fn\n  📥 2\n  📲\n", encoding="utf-8",
        )
        monkeypatch.setenv("EMOJIASM_PATH", str(lib_dir))
        source = "📦 mod\n📜 🏠\n  📞 fn\n  🖨️\n  🛑"
        out = _run(source, base_path=str(src_dir))
        assert "".join(out).strip() == "2"

    def test_multiple_env_path_entries(self, tmp_path, monkeypatch):
        dir1 = tmp_path / "d1"
        dir2 = tmp_path / "d2"
        dir1.mkdir()
        dir2.mkdir()
        (dir2 / "found.emoji").write_text(
            "📜 found_fn\n  📥 55\n  📲\n", encoding="utf-8",
        )
        monkeypatch.setenv("EMOJIASM_PATH", f"{dir1}{os.pathsep}{dir2}")
        source = "📦 found\n📜 🏠\n  📞 found_fn\n  🖨️\n  🛑"
        out = _run(source, base_path=str(tmp_path / "empty"))
        assert "".join(out).strip() == "55"


# ---------------------------------------------------------------------------
# 7. Empty import name raises
# ---------------------------------------------------------------------------

class TestImportEdgeCases:

    def test_empty_import_name_raises(self):
        with pytest.raises(ParseError, match="[Ii]mport requires"):
            parse("📦\n📜 🏠\n  🛑")

    def test_whitespace_only_import_name_raises(self):
        with pytest.raises(ParseError, match="[Ii]mport requires"):
            parse("📦   \n📜 🏠\n  🛑")

    def test_import_before_any_function(self, tmp_path):
        """📦 can appear before any 📜 directive — it is structural."""
        lib = tmp_path / "lib.emoji"
        lib.write_text("📜 helper\n  📥 1\n  📲\n", encoding="utf-8")
        source = "📦 lib\n📜 🏠\n  📞 helper\n  🖨️\n  🛑"
        out = _run(source, base_path=str(tmp_path))
        assert "".join(out).strip() == "1"

    def test_import_between_functions(self, tmp_path):
        """📦 can appear between function definitions."""
        lib = tmp_path / "lib.emoji"
        lib.write_text("📜 helper\n  📥 88\n  📲\n", encoding="utf-8")
        source = (
            "📜 🏠\n  📞 helper\n  🖨️\n  🛑\n"
            "📦 lib\n"
        )
        out = _run(source, base_path=str(tmp_path))
        assert "".join(out).strip() == "88"

    def test_multiple_imports(self, tmp_path):
        (tmp_path / "a.emoji").write_text("📜 afn\n  📥 10\n  📲\n", encoding="utf-8")
        (tmp_path / "b.emoji").write_text("📜 bfn\n  📥 20\n  📲\n", encoding="utf-8")
        source = "📦 a\n📦 b\n📜 🏠\n  📞 afn\n  📞 bfn\n  ➕\n  🖨️\n  🛑"
        out = _run(source, base_path=str(tmp_path))
        assert "".join(out).strip() == "30"


# ---------------------------------------------------------------------------
# 8. Diamond import (A imports B and C; both B and C import D)
# ---------------------------------------------------------------------------

class TestDiamondImport:

    def test_diamond_import_no_error(self, tmp_path):
        """Same module imported through two paths should not cause circular error."""
        (tmp_path / "d.emoji").write_text("📜 dfn\n  📥 1\n  📲\n", encoding="utf-8")
        (tmp_path / "b.emoji").write_text("📦 d\n📜 bfn\n  📞 dfn\n  📲\n", encoding="utf-8")
        (tmp_path / "c.emoji").write_text("📦 d\n📜 cfn\n  📞 dfn\n  📲\n", encoding="utf-8")
        source = "📦 b\n📦 c\n📜 🏠\n  📞 dfn\n  🖨️\n  🛑"
        out = _run(source, base_path=str(tmp_path))
        assert "".join(out).strip() == "1"


# ---------------------------------------------------------------------------
# 9. parse() backward compatibility (no new args required)
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:

    def test_parse_with_no_extra_args_still_works(self):
        """Existing code calling parse(source) must not break."""
        prog = parse("📜 🏠\n  📥 42\n  🖨️\n  🛑")
        assert "🏠" in prog.functions

    def test_parse_existing_tests_pattern(self):
        """Mimics the run() helper from test_emojiasm.py."""
        source = "📜 🏠\n  📥 3\n  📥 4\n  ➕\n  🖨️\n  🛑"
        program = parse(source)
        vm = VM(program)
        vm.max_steps = 10000
        out = vm.run()
        assert "".join(out).strip() == "7"
