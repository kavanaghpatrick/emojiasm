"""Agent mode: structured JSON output, parallel runs, and tracing for LLM agents."""

import io
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from contextlib import redirect_stdout
from dataclasses import dataclass, field

from .opcodes import Op, OP_TO_EMOJI
from .parser import Program
from .vm import VM, VMError


@dataclass
class TraceEntry:
    step: int
    func: str
    ip: int
    op: str
    stack: list

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "func": self.func,
            "ip": self.ip,
            "op": self.op,
            "stack": self.stack[-8:],  # last 8 elements max
        }


@dataclass
class InstanceResult:
    instance_id: int
    instance_seed: int
    status: str = "ok"
    exit_code: int | None = 0
    output: str | None = None
    time_ms: float = 0.0
    steps: int | None = None
    error: str | None = None
    traces: list[TraceEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "instance_seed": self.instance_seed,
            "status": self.status,
            "exit_code": self.exit_code,
            "output": self.output,
            "time_ms": round(self.time_ms, 2),
            "steps": self.steps,
            "error": self.error,
            "traces": [t.to_dict() for t in self.traces],
        }


class TracingVM(VM):
    """VM subclass that collects trace snapshots at configurable intervals."""

    def __init__(self, program: Program, trace_steps: int = 0, **kwargs):
        super().__init__(program, **kwargs)
        self.trace_steps = trace_steps
        self.traces: list[TraceEntry] = []
        self._current_func: str = ""
        self._current_ip: int = 0

    def _exec_function(self, entry_func: str):
        """Override to capture func/ip context for tracing."""
        if entry_func not in self.program.functions:
            raise VMError(f"Function '{entry_func}' not found")

        func_name = entry_func
        func = self.program.functions[func_name]
        ip = 0

        while not self.halted:
            if ip >= len(func.instructions):
                if not self.call_stack:
                    break
                func_name, ip = self.call_stack.pop()
                func = self.program.functions[func_name]
                continue

            self.steps += 1
            if self.steps > self.max_steps:
                raise VMError("Execution limit exceeded (infinite loop?) \U0001f501")

            inst = func.instructions[ip]
            op = inst.op
            arg = inst.arg

            # Trace snapshot
            if self.trace_steps > 0 and self.steps % self.trace_steps == 0:
                op_name = OP_TO_EMOJI.get(op, str(op))
                self.traces.append(TraceEntry(
                    step=self.steps,
                    func=func_name,
                    ip=ip,
                    op=op.name,
                    stack=list(self.stack),
                ))

            if self.debug:
                stack_preview = self.stack[-5:] if self.stack else []
                print(f"  \U0001f50d [{func_name}:{ip}] {inst.source}  stack={stack_preview}", file=sys.stderr)

            next_ip = ip + 1

            match op:
                case Op.PUSH:
                    self._push(arg)
                case Op.POP:
                    self._pop()
                case Op.ADD:
                    b, a = self._pop(), self._pop()
                    if isinstance(a, str) or isinstance(b, str):
                        self._push(str(a) + str(b))
                    else:
                        self._push(a + b)
                case Op.SUB:
                    b, a = self._pop(), self._pop()
                    self._push(a - b)
                case Op.MUL:
                    b, a = self._pop(), self._pop()
                    self._push(a * b)
                case Op.DIV:
                    b, a = self._pop(), self._pop()
                    if b == 0:
                        raise VMError("Division by zero", ip, source=inst.source, func_name=func_name)
                    if isinstance(a, int) and isinstance(b, int):
                        self._push(a // b)
                    else:
                        self._push(a / b)
                case Op.MOD:
                    b, a = self._pop(), self._pop()
                    if b == 0:
                        raise VMError("Modulo by zero", ip, source=inst.source, func_name=func_name)
                    self._push(a % b)
                case Op.PRINT:
                    val = self._pop()
                    out = str(val)
                    self.output_buffer.append(out)
                    print(out, end="")
                case Op.PRINTLN:
                    val = self._pop()
                    out = str(val)
                    self.output_buffer.append(out + "\n")
                    print(out)
                case Op.PRINTS:
                    self._push(str(arg))
                case Op.DUP:
                    self._push(self._peek())
                case Op.SWAP:
                    b, a = self._pop(), self._pop()
                    self._push(b)
                    self._push(a)
                case Op.OVER:
                    if len(self.stack) < 2:
                        raise VMError("Stack needs at least 2 elements for OVER", ip, source=inst.source, func_name=func_name)
                    self._push(self.stack[-2])
                case Op.ROT:
                    if len(self.stack) < 3:
                        raise VMError("Stack needs at least 3 elements for ROT", ip, source=inst.source, func_name=func_name)
                    c, b, a = self._pop(), self._pop(), self._pop()
                    self._push(b)
                    self._push(c)
                    self._push(a)
                case Op.JMP:
                    next_ip = self._resolve_label(func, arg)
                case Op.JZ:
                    val = self._pop()
                    if val == 0:
                        next_ip = self._resolve_label(func, arg)
                case Op.JNZ:
                    val = self._pop()
                    if val != 0:
                        next_ip = self._resolve_label(func, arg)
                case Op.CMP_EQ:
                    b, a = self._pop(), self._pop()
                    self._push(1 if a == b else 0)
                case Op.CMP_LT:
                    b, a = self._pop(), self._pop()
                    self._push(1 if a < b else 0)
                case Op.CMP_GT:
                    b, a = self._pop(), self._pop()
                    self._push(1 if a > b else 0)
                case Op.AND:
                    b, a = self._pop(), self._pop()
                    self._push(1 if (a and b) else 0)
                case Op.OR:
                    b, a = self._pop(), self._pop()
                    self._push(1 if (a or b) else 0)
                case Op.NOT:
                    a = self._pop()
                    self._push(1 if not a else 0)
                case Op.STORE:
                    self.memory[arg] = self._pop()
                case Op.LOAD:
                    if arg not in self.memory:
                        raise VMError(f"Memory address '{arg}' not initialized", ip, source=inst.source, func_name=func_name)
                    self._push(self.memory[arg])
                case Op.CALL:
                    if arg not in self.program.functions:
                        raise VMError(f"Function '{arg}' not found", ip, source=inst.source, func_name=func_name)
                    self.call_stack.append((func_name, next_ip))
                    func_name = arg
                    func = self.program.functions[func_name]
                    next_ip = 0
                case Op.RET:
                    if not self.call_stack:
                        break
                    func_name, next_ip = self.call_stack.pop()
                    func = self.program.functions[func_name]
                case Op.INPUT:
                    try:
                        self._push(input())
                    except EOFError:
                        self._push("")
                case Op.INPUT_NUM:
                    try:
                        self._push(int(input()))
                    except (EOFError, ValueError):
                        self._push(0)
                case Op.HALT:
                    self.halted = True
                    break
                case Op.NOP:
                    pass
                case _:
                    raise VMError(f"Unknown opcode: {op}", ip, source=inst.source, func_name=func_name)

            ip = next_ip


def _run_instance(program: Program, instance_id: int, seed: int,
                  max_steps: int, trace_steps: int) -> InstanceResult:
    """Run a single VM instance, capturing output and traces."""
    result = InstanceResult(instance_id=instance_id, instance_seed=seed)
    t0 = time.perf_counter()

    try:
        buf = io.StringIO()
        vm = TracingVM(program, trace_steps=trace_steps)
        vm.max_steps = max_steps

        with redirect_stdout(buf):
            vm.run()

        result.output = buf.getvalue()
        result.steps = vm.steps
        result.traces = vm.traces
        result.exit_code = 0
    except VMError as e:
        result.status = "error"
        result.exit_code = 1
        result.error = str(e)
        result.steps = None
    except Exception as e:
        result.status = "error"
        result.exit_code = 1
        result.error = f"Unexpected: {e}"

    result.time_ms = (time.perf_counter() - t0) * 1000
    return result


def run_agent_mode(program: Program, filename: str, runs: int = 1,
                   json_output: bool = True, trace_steps: int = 0,
                   timeout_ms: int = 0, seed: int | None = None,
                   max_steps: int = 1_000_000) -> dict:
    """Execute program in agent mode with parallel runs and structured output."""
    if seed is None:
        seed = random.randint(0, 2**31)

    instance_seeds = [seed + i for i in range(runs)]
    results: list[InstanceResult] = []

    wall_t0 = time.perf_counter()

    if runs == 1:
        # Single run — no thread overhead
        r = _run_instance(program, 0, instance_seeds[0], max_steps, trace_steps)
        if timeout_ms > 0 and r.time_ms > timeout_ms:
            r.status = "timeout"
            r.error = f"Timeout after {timeout_ms}ms"
        results.append(r)
    else:
        # Parallel runs via thread pool
        timeout_s = timeout_ms / 1000.0 if timeout_ms > 0 else None

        with ThreadPoolExecutor(max_workers=min(runs, 16)) as pool:
            futures = {
                pool.submit(_run_instance, program, i, instance_seeds[i],
                            max_steps, trace_steps): i
                for i in range(runs)
            }
            for future in futures:
                i = futures[future]
                try:
                    r = future.result(timeout=timeout_s)
                    results.append(r)
                except FuturesTimeout:
                    results.append(InstanceResult(
                        instance_id=i,
                        instance_seed=instance_seeds[i],
                        status="timeout",
                        exit_code=None,
                        error=f"Timeout after {timeout_ms}ms",
                        time_ms=float(timeout_ms),
                    ))
                except Exception as e:
                    results.append(InstanceResult(
                        instance_id=i,
                        instance_seed=instance_seeds[i],
                        status="error",
                        exit_code=1,
                        error=str(e),
                    ))

    results.sort(key=lambda r: r.instance_id)
    wall_ms = (time.perf_counter() - wall_t0) * 1000

    # Compute stats
    ok_count = sum(1 for r in results if r.status == "ok")
    error_count = sum(1 for r in results if r.status == "error")
    timeout_count = sum(1 for r in results if r.status == "timeout")

    # Try to extract numeric outputs for stats
    numeric_outputs = []
    for r in results:
        if r.status == "ok" and r.output:
            stripped = r.output.strip()
            try:
                numeric_outputs.append(float(stripped))
            except (ValueError, TypeError):
                pass

    stats: dict = {
        "ok_count": ok_count,
        "error_count": error_count,
        "timeout_count": timeout_count,
    }

    if numeric_outputs:
        stats["numeric_outputs"] = numeric_outputs
        stats["mean"] = sum(numeric_outputs) / len(numeric_outputs)
        if len(numeric_outputs) > 1:
            mean = stats["mean"]
            variance = sum((x - mean) ** 2 for x in numeric_outputs) / len(numeric_outputs)
            stats["std"] = variance ** 0.5
        else:
            stats["std"] = 0.0
        stats["min"] = min(numeric_outputs)
        stats["max"] = max(numeric_outputs)

    output = {
        "schema_version": "1",
        "program": filename,
        "instances": runs,
        "wall_time_ms": round(wall_ms, 2),
        "seed": seed,
        "results": [r.to_dict() for r in results],
        "stats": stats,
    }

    return output
