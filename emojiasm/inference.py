"""LLM inference integration for EmojiASM.

Provides EmojiASMTool for executing EmojiASM programs as an LLM tool,
with automatic GPU/CPU routing and zero-copy results on Apple Silicon.
"""

from __future__ import annotations

import json
import time
from typing import Any


class EmojiASMTool:
    """LLM tool that executes EmojiASM programs on GPU.

    Designed to be called between token generation steps.
    Results stay in GPU memory as mx.array for zero-copy
    feedback to the next prompt.
    """

    def __init__(
        self,
        max_instances: int = 10_000,
        max_steps: int = 1_000_000,
        prefer_gpu: bool = True,
    ):
        self.max_instances = max_instances
        self.max_steps = max_steps
        self.prefer_gpu = prefer_gpu

    def execute(self, source: str, n: int = 1) -> dict:
        """Parse and execute an EmojiASM program.

        Args:
            source: EmojiASM source code (from LLM output)
            n: Number of parallel instances (capped at max_instances)

        Returns:
            dict with keys: success, mode (gpu/cpu), instances, completed,
            failed, results, stats, total_time_ms, program_tier
        """
        t0 = time.perf_counter()
        n = min(max(n, 1), self.max_instances)

        # 1. Parse source
        try:
            from .parser import parse
            program = parse(source)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return {
                "success": False,
                "mode": "none",
                "instances": 0,
                "completed": 0,
                "failed": 0,
                "results": [],
                "stats": {},
                "total_time_ms": round(elapsed_ms, 2),
                "program_tier": None,
                "error": f"Parse error: {exc}",
            }

        return self._execute_program(program, n, t0)

    def execute_python(self, source: str, n: int = 1) -> dict:
        """Transpile Python source and execute as EmojiASM.

        Args:
            source: Python source code (subset: arithmetic, loops, random)
            n: Number of parallel instances (capped at max_instances)

        Returns:
            Same dict format as execute()
        """
        t0 = time.perf_counter()
        n = min(max(n, 1), self.max_instances)

        try:
            from .transpiler import transpile
            program = transpile(source)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return {
                "success": False,
                "mode": "none",
                "instances": 0,
                "completed": 0,
                "failed": 0,
                "results": [],
                "stats": {},
                "total_time_ms": round(elapsed_ms, 2),
                "program_tier": None,
                "error": f"Transpile error: {exc}",
            }

        return self._execute_program(program, n, t0)

    def _execute_program(self, program: Any, n: int, t0: float) -> dict:
        """Execute an already-parsed Program (shared by execute and execute_python)."""
        # 2. Get GPU tier
        try:
            from .bytecode import gpu_tier
            tier = gpu_tier(program)
        except Exception:
            tier = 3  # conservative fallback

        # 3. Route: GPU if tier<=2, n>=256, prefer_gpu, gpu_available(); else CPU
        use_gpu = False
        if self.prefer_gpu and tier <= 2 and n >= 256:
            try:
                from .gpu import gpu_available
                use_gpu = gpu_available()
            except Exception:
                use_gpu = False

        # 4. Execute and return structured result
        if use_gpu:
            return self._execute_gpu(program, n, tier, t0)
        else:
            return self._execute_cpu(program, n, tier, t0)

    def _execute_gpu(self, program: Any, n: int, tier: int, t0: float) -> dict:
        """Execute on GPU via MLX Metal kernel."""
        try:
            from .gpu import gpu_run
            result = gpu_run(program, n=n, max_steps=self.max_steps)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            result["total_time_ms"] = round(elapsed_ms, 2)
            result["program_tier"] = tier
            return result
        except Exception as exc:
            # Fall back to CPU on GPU failure
            return self._execute_cpu(program, n, tier, t0)

    def _execute_cpu(self, program: Any, n: int, tier: int, t0: float) -> dict:
        """Execute on CPU via agent mode."""
        try:
            from .agent import run_agent_mode
            agent_result = run_agent_mode(
                program, filename="<inference>", runs=n, max_steps=self.max_steps
            )
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
                1
                for r in agent_result.get("results", [])
                if r.get("status") == "ok"
            )

            # Compute stats
            stats = self._compute_stats(numeric_results)

            return {
                "success": ok_count == n,
                "mode": "cpu",
                "instances": n,
                "completed": ok_count,
                "failed": n - ok_count,
                "results": numeric_results,
                "stats": stats,
                "total_time_ms": round(elapsed_ms, 2),
                "program_tier": tier,
            }
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return {
                "success": False,
                "mode": "cpu",
                "instances": n,
                "completed": 0,
                "failed": n,
                "results": [],
                "stats": {},
                "total_time_ms": round(elapsed_ms, 2),
                "program_tier": tier,
                "error": f"Execution error: {exc}",
            }

    @staticmethod
    def _compute_stats(values: list[float]) -> dict:
        """Compute summary statistics from a list of float values."""
        import math

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

    def execute_batch(self, sources: list[str], n_each: int = 1) -> list[dict]:
        """Execute multiple programs, returning results for each."""
        return [self.execute(src, n=n_each) for src in sources]

    def validate(self, source: str) -> dict:
        """Validate EmojiASM source without executing.

        Returns: {valid: bool, error: str|None, tier: int,
                  num_instructions: int, gpu_compatible: bool}
        """
        try:
            from .parser import parse
            program = parse(source)
        except Exception as exc:
            return {
                "valid": False,
                "error": str(exc),
                "tier": None,
                "num_instructions": 0,
                "gpu_compatible": False,
            }

        try:
            from .bytecode import gpu_tier
            tier = gpu_tier(program)
        except Exception:
            tier = 3

        num_instructions = sum(
            len(func.instructions) for func in program.functions.values()
        )

        return {
            "valid": True,
            "error": None,
            "tier": tier,
            "num_instructions": num_instructions,
            "gpu_compatible": tier <= 2,
        }

    def as_tool_spec(self) -> dict:
        """Return OpenAI-compatible tool specification for function calling.

        The description embeds a compact language reference so the LLM
        can write valid EmojiASM programs without external documentation.
        """
        return {
            "type": "function",
            "function": {
                "name": "emojiasm_execute",
                "description": _TOOL_DESCRIPTION,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "EmojiASM source code using emoji opcodes. Must start with 📜 🏠 and end with 🛑.",
                        },
                        "instances": {
                            "type": "integer",
                            "description": (
                                "Number of parallel GPU instances. Use 1 for single runs, "
                                "1000+ for Monte Carlo / sampling. Each instance runs the "
                                "same program independently with its own PRNG seed."
                            ),
                            "default": 1,
                        },
                    },
                    "required": ["source"],
                },
            },
        }

    def as_system_prompt(self) -> str:
        """Return a system prompt that teaches an LLM to write EmojiASM.

        Use this to prepend to your LLM's system prompt so it can generate
        valid EmojiASM programs when asked to perform computations.
        """
        return _SYSTEM_PROMPT

    def handle_tool_call(self, tool_call: dict) -> dict:
        """Handle an OpenAI-format tool call.

        Args:
            tool_call: dict with 'arguments' key containing 'source'
                       and optional 'instances'

        Returns:
            Execution result dict
        """
        args = tool_call.get("arguments", {})
        if isinstance(args, str):
            args = json.loads(args)
        source = args.get("source", "")
        n = min(args.get("instances", 1), self.max_instances)
        return self.execute(source, n=n)


# ── Embedded language reference for LLM tool specs ───────────────────────

_TOOL_DESCRIPTION = """\
Execute an EmojiASM program on GPU (Apple Silicon) or CPU. \
Each instance runs independently with its own PRNG seed — use instances>1 for Monte Carlo sampling, parameter sweeps, or statistical bootstrapping.

## EmojiASM Quick Reference

Stack-based assembly. Every program starts with `📜 🏠` and ends with `🛑`. \
Values go on a stack; operations pop inputs and push results.

### Opcodes

Stack: 📥 val (push) · 📤 (pop) · 📋 (dup) · 🔀 (swap) · 🫴 (over) · 🔄 (rot)
Math: ➕ (add) · ➖ (sub) · ✖️ (mul) · ➗ (div) · 🔢 (mod) · 🎲 (random 0.0–1.0)
Compare: 🟰 (eq→0|1) · 📏 (lt→0|1) · 📐 (gt→0|1) · 🤝 (and) · 🤙 (or) · 🚫 (not)
Control: 👉 lbl (jmp) · 🤔 lbl (jz) · 😤 lbl (jnz) · 📞 fn (call) · 📲 (ret) · 🛑 (halt) · 💤 (nop)
I/O: 📢 (print) · 🖨️ (println) · 💬 "text" (push string)
Memory: 💾 cell (store) · 📂 cell (load) — cell names are emoji
Labels: 🏷️ name — jump targets within a function
Comments: 💭 text — ignored

### Key rules
- 🤔/😤 CONSUME the condition — 📋 DUP first if you still need it
- 📂 LOAD on unwritten cell crashes — always 💾 STORE first
- ➗ DIV: integer // integer = floor division; use 📥 1.0 for float
- 🎲 RANDOM pushes float in [0.0, 1.0); each GPU thread has its own seed
- Top of stack at 🛑 becomes the result

### Example: Monte Carlo Pi (run with instances=10000)
```
📜 🏠
  📥 0  💾 🔢
  📥 0  💾 📊
  📥 10000  💾 🎯
  🏷️ 🔁
    📂 📊  📂 🎯  🟰  😤 🏁
    🎲  📋  ✖️
    🎲  📋  ✖️
    ➕  📥 1.0  📐  🚫
    🤔 ⭕
    📂 🔢  📥 1  ➕  💾 🔢
    🏷️ ⭕
    📂 📊  📥 1  ➕  💾 📊
    👉 🔁
  🏷️ 🏁
  📂 🔢  📥 4.0  ✖️  📂 🎯  ➗  🛑
```

### Example: Multiply two numbers
```
📜 🏠
  📥 6
  📥 7
  ✖️
  🛑
```

### Example: Random sampling (run with instances=1000)
```
📜 🏠
  🎲
  📋
  ✖️
  🛑
```
Each instance pushes a random x, computes x², returns it. Stats show the distribution.

### Pattern: While loop
```
📥 0  💾 🔢          💭 i = 0
🏷️ 🔁               💭 loop start
  📂 🔢  📥 10  🟰   💭 i == 10?
  😤 🏁              💭 exit when true
  [body]
  📂 🔢  📥 1  ➕  💾 🔢  💭 i++
  👉 🔁
🏷️ 🏁               💭 loop end
```\
"""

_SYSTEM_PROMPT = """\
You have access to EmojiASM, a GPU-accelerated stack-based assembly language made of emoji. \
Use it when you need to run massively parallel computations — Monte Carlo simulations, \
parameter sweeps, statistical bootstrapping, or any task that benefits from 1,000–10,000+ \
independent runs.

""" + _TOOL_DESCRIPTION + """

## When to use EmojiASM
- Monte Carlo estimation (pi, integrals, probabilities)
- Parameter sweep: run same formula with different random inputs
- Statistical bootstrapping: resample and compute statistics
- Risk simulation: model outcomes across thousands of scenarios
- Any numeric computation that benefits from massive parallelism

## When NOT to use EmojiASM
- String processing or text manipulation (use Python)
- File I/O, network requests, or system commands
- Single-run computations (just compute directly)
- Complex data structures (EmojiASM has a flat stack + 32 memory cells)

## Tips for writing EmojiASM
1. Think in terms of stack operations: push values, operate, result stays on stack
2. Use 💾/📂 with emoji names for variables (e.g., 💾 🔢 stores top of stack into cell 🔢)
3. Loops: 🏷️ marks a label, 👉 jumps back, 🤔/😤 for conditional exit
4. 🎲 gives a random float [0,1) — each GPU thread gets different values
5. The value on top of the stack when 🛑 executes becomes the per-thread result
6. For parallel runs, set instances=1000+ so GPU acceleration kicks in
"""
