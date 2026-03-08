"""Stack-based virtual machine for EmojiASM."""

import math
import random
import sys
from .opcodes import Op
from .parser import Program, Function


class VMError(Exception):
    def __init__(self, message: str, ip: int = -1, source: str = "", func_name: str = ""):
        self.ip = ip
        self.source = source
        self.func_name = func_name
        loc = f" in {func_name}" if func_name else ""
        src = f"\n   → {source}" if source else ""
        super().__init__(f"💀 Runtime error at IP={ip}{loc}: {message}{src}")


class VM:
    def __init__(self, program: Program, stack_size: int = 4096, debug: bool = False):
        self.program = program
        self.stack: list = []
        self.memory: dict[str, object] = {}
        self.call_stack: list[tuple[str, int]] = []
        self.debug = debug
        self.max_stack = stack_size
        self.output_buffer: list[str] = []
        self.halted = False
        self.steps = 0
        self.max_steps = 1_000_000

    def _push(self, value):
        if len(self.stack) >= self.max_stack:
            raise VMError("Stack overflow 💥")
        self.stack.append(value)

    def _pop(self):
        if not self.stack:
            raise VMError("Stack underflow 🕳️")
        return self.stack.pop()

    def _peek(self):
        if not self.stack:
            raise VMError("Stack empty 🕳️")
        return self.stack[-1]

    def _resolve_label(self, func: Function, label: str) -> int:
        if label not in func.labels:
            raise VMError(f"Unknown label: {label}")
        return func.labels[label]

    def run(self):
        """Execute the program starting from the entry point."""
        entry = self.program.entry_point
        if entry not in self.program.functions:
            raise VMError(f"Entry point '{entry}' not found")

        self._exec_function(entry)
        return self.output_buffer

    def _exec_function(self, entry_func: str):
        if entry_func not in self.program.functions:
            raise VMError(f"Function '{entry_func}' not found")

        func_name = entry_func
        func = self.program.functions[func_name]
        ip = 0

        while not self.halted:
            # Implicit return when falling off the end of a function
            if ip >= len(func.instructions):
                if not self.call_stack:
                    break
                func_name, ip = self.call_stack.pop()
                func = self.program.functions[func_name]
                continue

            self.steps += 1
            if self.steps > self.max_steps:
                raise VMError("Execution limit exceeded (infinite loop?) 🔁")

            inst = func.instructions[ip]
            op = inst.op
            arg = inst.arg

            if self.debug:
                stack_preview = self.stack[-5:] if self.stack else []
                print(f"  🔍 [{func_name}:{ip}] {inst.source}  stack={stack_preview}", file=sys.stderr)

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
                        raise VMError("Division by zero ➗💥", ip, source=inst.source, func_name=func_name)
                    if isinstance(a, int) and isinstance(b, int):
                        self._push(a // b)
                    else:
                        self._push(a / b)

                case Op.MOD:
                    b, a = self._pop(), self._pop()
                    if b == 0:
                        raise VMError("Modulo by zero 🔢💥", ip, source=inst.source, func_name=func_name)
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
                        raise VMError(f"Memory address '{arg}' not initialized 📂❌", ip, source=inst.source, func_name=func_name)
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
                        val = input()
                    except EOFError:
                        raise VMError("Invalid numeric input: <EOF>", ip, source=inst.source, func_name=func_name)
                    try:
                        self._push(int(val))
                    except ValueError:
                        try:
                            self._push(float(val))
                        except ValueError:
                            raise VMError(f"Invalid numeric input: {val}", ip, source=inst.source, func_name=func_name)

                case Op.HALT:
                    self.halted = True
                    break

                case Op.NOP:
                    pass

                case Op.STRLEN:
                    s = self._pop()
                    if not isinstance(s, str):
                        raise VMError("STRLEN requires a string", ip, source=inst.source, func_name=func_name)
                    self._push(len(s))

                case Op.SUBSTR:
                    length = self._pop()
                    start = self._pop()
                    s = self._pop()
                    if not isinstance(s, str):
                        raise VMError("SUBSTR requires a string", ip, source=inst.source, func_name=func_name)
                    self._push(s[int(start):int(start)+int(length)])

                case Op.STRINDEX:
                    sub = self._pop()
                    s = self._pop()
                    self._push(str(s).find(str(sub)))

                case Op.STR2NUM:
                    s = self._pop()
                    if not isinstance(s, str):
                        raise VMError("STR2NUM requires a string", ip, source=inst.source, func_name=func_name)
                    try:
                        self._push(int(s))
                    except ValueError:
                        try:
                            self._push(float(s))
                        except ValueError:
                            raise VMError(f"STR2NUM: cannot parse '{s}' as number", ip, source=inst.source, func_name=func_name)

                case Op.NUM2STR:
                    n = self._pop()
                    self._push(str(n))

                case Op.RANDOM:
                    self._push(random.random())

                case Op.POW:
                    b, a = self._pop(), self._pop()
                    self._push(a ** b)

                case Op.SQRT:
                    a = self._pop()
                    try:
                        self._push(math.sqrt(a))
                    except ValueError:
                        raise VMError(f"SQRT of negative number: {a}", ip, source=inst.source, func_name=func_name)

                case Op.SIN:
                    a = self._pop()
                    self._push(math.sin(a))

                case Op.COS:
                    a = self._pop()
                    self._push(math.cos(a))

                case Op.EXP:
                    a = self._pop()
                    self._push(math.exp(a))

                case Op.LOG:
                    a = self._pop()
                    try:
                        self._push(math.log(a))
                    except ValueError:
                        raise VMError(f"LOG domain error: {a}", ip, source=inst.source, func_name=func_name)

                case Op.ABS:
                    a = self._pop()
                    self._push(abs(a))

                case Op.MIN:
                    b, a = self._pop(), self._pop()
                    self._push(min(a, b))

                case Op.MAX:
                    b, a = self._pop(), self._pop()
                    self._push(max(a, b))

                case Op.ALLOC:
                    size = self._pop()
                    isize = int(size)
                    if isize < 0:
                        raise VMError(f"ALLOC size must be non-negative, got {size}", ip, source=inst.source, func_name=func_name)
                    self.memory[arg] = [0.0] * isize

                case Op.ALOAD:
                    if arg not in self.memory:
                        raise VMError(f"Cell '{arg}' not initialized 📂❌", ip, source=inst.source, func_name=func_name)
                    arr = self.memory[arg]
                    if not isinstance(arr, list):
                        raise VMError(f"Cell '{arg}' is not an array", ip, source=inst.source, func_name=func_name)
                    idx = int(self._pop())
                    if idx < 0 or idx >= len(arr):
                        raise VMError(f"Array index {idx} out of bounds for '{arg}' (size {len(arr)})", ip, source=inst.source, func_name=func_name)
                    self._push(arr[idx])

                case Op.ASTORE:
                    if arg not in self.memory:
                        raise VMError(f"Cell '{arg}' not initialized 📂❌", ip, source=inst.source, func_name=func_name)
                    arr = self.memory[arg]
                    if not isinstance(arr, list):
                        raise VMError(f"Cell '{arg}' is not an array", ip, source=inst.source, func_name=func_name)
                    val = self._pop()
                    idx = int(self._pop())
                    if idx < 0 or idx >= len(arr):
                        raise VMError(f"Array index {idx} out of bounds for '{arg}' (size {len(arr)})", ip, source=inst.source, func_name=func_name)
                    arr[idx] = val

                case Op.ALEN:
                    if arg not in self.memory:
                        raise VMError(f"Cell '{arg}' not initialized 📂❌", ip, source=inst.source, func_name=func_name)
                    arr = self.memory[arg]
                    if not isinstance(arr, list):
                        raise VMError(f"Cell '{arg}' is not an array", ip, source=inst.source, func_name=func_name)
                    self._push(len(arr))

                case _:
                    raise VMError(f"Unknown opcode: {op}", ip, source=inst.source, func_name=func_name)

            ip = next_ip
