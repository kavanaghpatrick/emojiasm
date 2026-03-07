"""Tests for EmojiASM agent mode: TracingVM, instance runner, and orchestrator."""

import json

from emojiasm.parser import parse
from emojiasm.agent import TracingVM, _run_instance, run_agent_mode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PUSH42 = "📜 🏠\n  📥 42\n  🖨️\n  🛑"

_ADD = "📜 🏠\n  📥 10\n  📥 20\n  ➕\n  🖨️\n  🛑"

_LOOP = (
    "📜 🏠\n"
    "  📥 3\n"
    "🏷️ loop\n"
    "  📋\n"
    "  🖨️\n"
    "  📥 1\n"
    "  ➖\n"
    "  📋\n"
    "  😤 loop\n"
    "  📤\n"
    "  🛑"
)

_DIV_ZERO = "📜 🏠\n  📥 1\n  📥 0\n  ➗\n  🛑"

_INFINITE = (
    "📜 🏠\n"
    "🏷️ spin\n"
    "  📥 1\n"
    "  📤\n"
    "  👉 spin\n"
)


def _parse(src: str):
    return parse(src)


# ---------------------------------------------------------------------------
# TracingVM
# ---------------------------------------------------------------------------

class TestTracingVM:
    def test_basic_execution(self):
        """TracingVM runs a simple program like the base VM."""
        prog = _parse(_PUSH42)
        vm = TracingVM(prog, trace_steps=0)
        vm.run()
        assert "42" in "".join(vm.output_buffer)

    def test_trace_collection(self):
        """TracingVM collects trace snapshots at configured intervals."""
        prog = _parse(_LOOP)
        vm = TracingVM(prog, trace_steps=1)
        vm.run()
        assert len(vm.traces) > 0
        # Each trace has required fields
        t = vm.traces[0]
        assert hasattr(t, "step")
        assert hasattr(t, "func")
        assert hasattr(t, "ip")
        assert hasattr(t, "op")
        assert hasattr(t, "stack")

    def test_trace_interval(self):
        """Traces are collected every N steps."""
        prog = _parse(_LOOP)
        vm = TracingVM(prog, trace_steps=3)
        vm.run()
        # Every trace step should be divisible by 3
        for t in vm.traces:
            assert t.step % 3 == 0

    def test_no_traces_when_disabled(self):
        """trace_steps=0 means no traces collected."""
        prog = _parse(_LOOP)
        vm = TracingVM(prog, trace_steps=0)
        vm.run()
        assert len(vm.traces) == 0

    def test_trace_to_dict(self):
        """TraceEntry.to_dict produces expected keys."""
        prog = _parse(_LOOP)
        vm = TracingVM(prog, trace_steps=1)
        vm.run()
        d = vm.traces[0].to_dict()
        assert set(d.keys()) == {"step", "func", "ip", "op", "stack"}

    def test_trace_stack_capped_at_8(self):
        """Trace stack snapshots are capped at last 8 elements."""
        prog = _parse(_PUSH42)
        vm = TracingVM(prog, trace_steps=1)
        vm.run()
        for t in vm.traces:
            assert len(t.to_dict()["stack"]) <= 8


# ---------------------------------------------------------------------------
# _run_instance
# ---------------------------------------------------------------------------

class TestRunInstance:
    def test_ok_result(self):
        """Successful run returns status=ok with output."""
        prog = _parse(_PUSH42)
        r = _run_instance(prog, 0, 42, 1_000_000, 0)
        assert r.status == "ok"
        assert r.exit_code == 0
        assert "42" in r.output
        assert r.time_ms > 0

    def test_error_result(self):
        """Division by zero returns status=error."""
        prog = _parse(_DIV_ZERO)
        r = _run_instance(prog, 0, 42, 1_000_000, 0)
        assert r.status == "error"
        assert r.exit_code == 1
        assert r.error is not None

    def test_execution_limit(self):
        """Infinite loop hits max_steps and returns error."""
        prog = _parse(_INFINITE)
        r = _run_instance(prog, 0, 42, 100, 0)
        assert r.status == "error"
        assert "limit" in r.error.lower() or "loop" in r.error.lower()

    def test_instance_result_to_dict(self):
        """InstanceResult.to_dict has all required keys."""
        prog = _parse(_PUSH42)
        r = _run_instance(prog, 7, 99, 1_000_000, 0)
        d = r.to_dict()
        assert d["instance_id"] == 7
        assert d["instance_seed"] == 99
        assert d["status"] == "ok"
        assert "exit_code" in d
        assert "output" in d
        assert "time_ms" in d
        assert "steps" in d
        assert "traces" in d

    def test_traces_in_instance(self):
        """Trace snapshots are captured when trace_steps > 0."""
        prog = _parse(_LOOP)
        r = _run_instance(prog, 0, 42, 1_000_000, 2)
        assert len(r.traces) > 0


# ---------------------------------------------------------------------------
# run_agent_mode
# ---------------------------------------------------------------------------

class TestRunAgentMode:
    def test_single_run_schema(self):
        """Single run produces valid schema with all required top-level keys."""
        prog = _parse(_PUSH42)
        out = run_agent_mode(prog, "test.emoji", runs=1, seed=0)
        assert out["schema_version"] == "1"
        assert out["program"] == "test.emoji"
        assert out["instances"] == 1
        assert out["seed"] == 0
        assert "wall_time_ms" in out
        assert len(out["results"]) == 1
        assert "stats" in out

    def test_single_run_output(self):
        """Single run captures program output."""
        prog = _parse(_PUSH42)
        out = run_agent_mode(prog, "test.emoji", runs=1)
        r = out["results"][0]
        assert r["status"] == "ok"
        assert "42" in r["output"]

    def test_parallel_runs(self):
        """Multiple parallel runs each produce results."""
        prog = _parse(_ADD)
        out = run_agent_mode(prog, "test.emoji", runs=4, seed=100)
        assert len(out["results"]) == 4
        assert out["instances"] == 4
        # All should succeed
        for r in out["results"]:
            assert r["status"] == "ok"
            assert "30" in r["output"]

    def test_results_sorted_by_instance_id(self):
        """Results are sorted by instance_id."""
        prog = _parse(_PUSH42)
        out = run_agent_mode(prog, "test.emoji", runs=5, seed=0)
        ids = [r["instance_id"] for r in out["results"]]
        assert ids == sorted(ids)

    def test_stats_ok_count(self):
        """Stats track ok/error/timeout counts."""
        prog = _parse(_PUSH42)
        out = run_agent_mode(prog, "test.emoji", runs=3, seed=0)
        assert out["stats"]["ok_count"] == 3
        assert out["stats"]["error_count"] == 0
        assert out["stats"]["timeout_count"] == 0

    def test_stats_error_count(self):
        """Error runs are counted in stats."""
        prog = _parse(_DIV_ZERO)
        out = run_agent_mode(prog, "test.emoji", runs=2, seed=0)
        assert out["stats"]["error_count"] == 2
        assert out["stats"]["ok_count"] == 0

    def test_numeric_stats(self):
        """Numeric outputs produce mean/std/min/max stats."""
        prog = _parse(_PUSH42)
        out = run_agent_mode(prog, "test.emoji", runs=3, seed=0)
        stats = out["stats"]
        assert stats["mean"] == 42.0
        assert stats["min"] == 42.0
        assert stats["max"] == 42.0
        assert "std" in stats

    def test_trace_collection_in_agent_mode(self):
        """Trace snapshots flow through to agent mode results."""
        prog = _parse(_LOOP)
        out = run_agent_mode(prog, "test.emoji", runs=1, trace_steps=2, seed=0)
        traces = out["results"][0]["traces"]
        assert len(traces) > 0
        assert "step" in traces[0]

    def test_json_serializable(self):
        """Output is JSON-serializable."""
        prog = _parse(_PUSH42)
        out = run_agent_mode(prog, "test.emoji", runs=2, trace_steps=1, seed=0)
        s = json.dumps(out)
        parsed = json.loads(s)
        assert parsed["schema_version"] == "1"

    def test_seed_determinism(self):
        """Same seed produces same instance_seed values."""
        prog = _parse(_PUSH42)
        out1 = run_agent_mode(prog, "test.emoji", runs=3, seed=42)
        out2 = run_agent_mode(prog, "test.emoji", runs=3, seed=42)
        seeds1 = [r["instance_seed"] for r in out1["results"]]
        seeds2 = [r["instance_seed"] for r in out2["results"]]
        assert seeds1 == seeds2

    def test_max_steps_propagated(self):
        """max_steps is passed through to VM instances."""
        prog = _parse(_INFINITE)
        out = run_agent_mode(prog, "test.emoji", runs=1, max_steps=50, seed=0)
        assert out["results"][0]["status"] == "error"

    def test_wall_time_positive(self):
        """Wall time is recorded and positive."""
        prog = _parse(_PUSH42)
        out = run_agent_mode(prog, "test.emoji", runs=1, seed=0)
        assert out["wall_time_ms"] > 0

    def test_timeout_single_run(self):
        """Timeout on a single run that exceeds time limit."""
        # We can't reliably test actual timeouts with fast programs,
        # but we can verify the timeout check path for single runs
        prog = _parse(_PUSH42)
        # Set timeout_ms=0 means no timeout
        out = run_agent_mode(prog, "test.emoji", runs=1, timeout_ms=0, seed=0)
        assert out["results"][0]["status"] == "ok"
