"""Tests for scripts/emoji_agent_runner.py — parallel runner for LLM agents."""

import json
import os
import subprocess
import sys

import pytest

# Add scripts/ to path so we can import the runner
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from emoji_agent_runner import run_parallel, _extract_number, _stats


# ---------------------------------------------------------------------------
# _extract_number
# ---------------------------------------------------------------------------

class TestExtractNumber:
    def test_plain(self):
        assert _extract_number("90") == 90.0

    def test_last_token(self):
        assert _extract_number("Computing result: 90") == 90.0

    def test_multiline(self):
        assert _extract_number("0 1 1 2 3 5 8\n4181") == 4181.0

    def test_no_number(self):
        assert _extract_number("Hello world") is None

    def test_empty_string(self):
        assert _extract_number("") is None

    def test_whitespace_only(self):
        assert _extract_number("   \n  \n") is None

    def test_float(self):
        assert _extract_number("pi is 3.14159") == 3.14159

    def test_trailing_punctuation(self):
        assert _extract_number("result: 42.") == 42.0

    def test_negative(self):
        assert _extract_number("-5") == -5.0

    def test_last_line_wins(self):
        assert _extract_number("10\n20\n30") == 30.0


# ---------------------------------------------------------------------------
# _stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_basic(self):
        s = _stats([1.0, 2.0, 3.0])
        assert s["count"] == 3
        assert s["mean"] == 2.0
        assert s["min"] == 1.0
        assert s["max"] == 3.0

    def test_empty(self):
        s = _stats([])
        assert s["count"] == 0
        assert s["mean"] == 0.0

    def test_single_value(self):
        s = _stats([42.0])
        assert s["count"] == 1
        assert s["mean"] == 42.0
        assert s["std"] == 0.0

    def test_std_nonzero(self):
        s = _stats([0.0, 10.0])
        assert s["std"] == 5.0


# ---------------------------------------------------------------------------
# run_parallel
# ---------------------------------------------------------------------------

class TestRunParallel:
    def test_file_not_found(self):
        r = run_parallel("/nonexistent/bad.emoji", n=1)
        assert r["success"] is False
        assert "not found" in r["error"].lower()

    def test_interpreted_math(self, tmp_path):
        src = tmp_path / "math.emoji"
        src.write_text("📜 🏠\n  📥 6\n  📥 7\n  ✖️\n  🖨️\n  🛑\n", encoding="utf-8")
        r = run_parallel(str(src), n=4, force_interpret=True, workers=2)
        assert r["success"] is True
        assert r["results"] == [42.0] * 4
        assert r["mode"] == "interpreted"

    def test_non_numeric_output(self, tmp_path):
        src = tmp_path / "hello.emoji"
        src.write_text('📜 🏠\n  💬 "Hello"\n  📢\n  🛑\n', encoding="utf-8")
        r = run_parallel(str(src), n=3, force_interpret=True, workers=2)
        assert r["success"] is True
        assert r["results"] == []
        assert r["stats"]["count"] == 0

    def test_json_serializable(self, tmp_path):
        src = tmp_path / "simple.emoji"
        src.write_text("📜 🏠\n  📥 99\n  🖨️\n  🛑\n", encoding="utf-8")
        r = run_parallel(str(src), n=2, force_interpret=True, workers=2)
        json.loads(json.dumps(r))  # must not raise

    def test_message_field(self, tmp_path):
        src = tmp_path / "nop.emoji"
        src.write_text("📜 🏠\n  📥 1\n  🖨️\n  🛑\n", encoding="utf-8")
        r = run_parallel(str(src), n=2, force_interpret=True, workers=2)
        assert r["message"] == "Ready for next agent iteration"

    def test_completed_plus_failed_equals_instances(self, tmp_path):
        src = tmp_path / "ok.emoji"
        src.write_text("📜 🏠\n  📥 1\n  🖨️\n  🛑\n", encoding="utf-8")
        r = run_parallel(str(src), n=5, force_interpret=True, workers=2)
        assert r["completed"] + r["failed"] == r["instances"]

    def test_parse_error(self, tmp_path):
        src = tmp_path / "bad.emoji"
        src.write_text("this is not valid emojiasm", encoding="utf-8")
        r = run_parallel(str(src), n=1, force_interpret=True)
        assert r["success"] is False
        assert "parse" in r["error"].lower() or "error" in r["error"].lower()

    def test_total_time_positive(self, tmp_path):
        src = tmp_path / "t.emoji"
        src.write_text("📜 🏠\n  📥 1\n  🖨️\n  🛑\n", encoding="utf-8")
        r = run_parallel(str(src), n=2, force_interpret=True, workers=2)
        assert r["total_time_ms"] > 0

    def test_stats_populated(self, tmp_path):
        src = tmp_path / "s.emoji"
        src.write_text("📜 🏠\n  📥 55\n  🖨️\n  🛑\n", encoding="utf-8")
        r = run_parallel(str(src), n=3, force_interpret=True, workers=2)
        assert r["stats"]["mean"] == 55.0
        assert r["stats"]["count"] == 3

    def test_workers_field(self, tmp_path):
        src = tmp_path / "w.emoji"
        src.write_text("📜 🏠\n  📥 1\n  🖨️\n  🛑\n", encoding="utf-8")
        r = run_parallel(str(src), n=2, workers=3, force_interpret=True)
        assert r["workers"] == 3


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCLI:
    @pytest.fixture(autouse=True)
    def _cli_env(self):
        """Set PYTHONPATH so subprocess can import emojiasm."""
        self._project_root = os.path.join(os.path.dirname(__file__), "..")
        self._env = {**os.environ, "PYTHONPATH": self._project_root}

    def test_cli_basic(self, tmp_path):
        src = tmp_path / "cli.emoji"
        src.write_text("📜 🏠\n  📥 42\n  🖨️\n  🛑\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "scripts/emoji_agent_runner.py", str(src),
             "--n", "2", "--no-compile"],
            capture_output=True, text=True, timeout=30,
            cwd=self._project_root, env=self._env,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["results"] == [42.0, 42.0]

    def test_cli_output_file(self, tmp_path):
        src = tmp_path / "out.emoji"
        src.write_text("📜 🏠\n  📥 7\n  🖨️\n  🛑\n", encoding="utf-8")
        out_file = tmp_path / "result.json"
        result = subprocess.run(
            [sys.executable, "scripts/emoji_agent_runner.py", str(src),
             "--n", "2", "--no-compile", "--output", str(out_file)],
            capture_output=True, text=True, timeout=30,
            cwd=self._project_root, env=self._env,
        )
        assert result.returncode == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["success"] is True

    def test_cli_file_not_found(self):
        result = subprocess.run(
            [sys.executable, "scripts/emoji_agent_runner.py", "/nonexistent.emoji",
             "--n", "1", "--no-compile"],
            capture_output=True, text=True, timeout=30,
            cwd=self._project_root, env=self._env,
        )
        assert result.returncode != 0
        data = json.loads(result.stdout)
        assert data["success"] is False

    def test_cli_compact(self, tmp_path):
        src = tmp_path / "c.emoji"
        src.write_text("📜 🏠\n  📥 1\n  🖨️\n  🛑\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "scripts/emoji_agent_runner.py", str(src),
             "--n", "1", "--no-compile", "--compact"],
            capture_output=True, text=True, timeout=30,
            cwd=self._project_root, env=self._env,
        )
        assert result.returncode == 0
        # Compact means no indentation — single line
        assert "\n" not in result.stdout.strip()
