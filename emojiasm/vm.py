"""Stack-based virtual machine for EmojiASM."""

import sys
from .opcodes import Op
from .parser import Program, Function


class VMError(Exception):
    def __init__(self, message: str, ip: int = -1):
        super().__init__(f"💀 Runtime error at IP={ip}: {message}")


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

    def _exec_function(self, func_name: str):
        if func_name not in self.program.functions:
            raise VMError(f"Function '{func_name}' not found")

        func = self.program.functions[func_name]
        ip = 0

        while ip < len(func.instructions) and not self.halted:
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

            if op == Op.PUSH:
                self._push(arg)

            elif op == Op.POP:
                self._pop()

            elif op == Op.ADD:
                b, a = self._pop(), self._pop()
                if isinstance(a, str) or isinstance(b, str):
                    self._push(str(a) + str(b))
                else:
                    self._push(a + b)

            elif op == Op.SUB:
                b, a = self._pop(), self._pop()
                self._push(a - b)

            elif op == Op.MUL:
                b, a = self._pop(), self._pop()
                self._push(a * b)

            elif op == Op.DIV:
                b, a = self._pop(), self._pop()
                if b == 0:
                    raise VMError("Division by zero ➗💥", ip)
                if isinstance(a, int) and isinstance(b, int):
                    self._push(a // b)
                else:
                    self._push(a / b)

            elif op == Op.MOD:
                b, a = self._pop(), self._pop()
                if b == 0:
                    raise VMError("Modulo by zero 🔢💥", ip)
                self._push(a % b)

            elif op == Op.PRINT:
                val = self._pop()
                out = str(val)
                self.output_buffer.append(out)
                print(out, end="")

            elif op == Op.PRINTLN:
                val = self._pop()
                out = str(val)
                self.output_buffer.append(out + "\n")
                print(out)

            elif op == Op.PRINTS:
                out = str(arg)
                self._push(out)

            elif op == Op.DUP:
                self._push(self._peek())

            elif op == Op.SWAP:
                b, a = self._pop(), self._pop()
                self._push(b)
                self._push(a)

            elif op == Op.OVER:
                if len(self.stack) < 2:
                    raise VMError("Stack needs at least 2 elements for OVER", ip)
                self._push(self.stack[-2])

            elif op == Op.ROT:
                if len(self.stack) < 3:
                    raise VMError("Stack needs at least 3 elements for ROT", ip)
                c, b, a = self._pop(), self._pop(), self._pop()
                self._push(b)
                self._push(c)
                self._push(a)

            elif op == Op.JMP:
                next_ip = self._resolve_label(func, arg)

            elif op == Op.JZ:
                val = self._pop()
                if val == 0:
                    next_ip = self._resolve_label(func, arg)

            elif op == Op.JNZ:
                val = self._pop()
                if val != 0:
                    next_ip = self._resolve_label(func, arg)

            elif op == Op.CMP_EQ:
                b, a = self._pop(), self._pop()
                self._push(1 if a == b else 0)

            elif op == Op.CMP_LT:
                b, a = self._pop(), self._pop()
                self._push(1 if a < b else 0)

            elif op == Op.CMP_GT:
                b, a = self._pop(), self._pop()
                self._push(1 if a > b else 0)

            elif op == Op.AND:
                b, a = self._pop(), self._pop()
                self._push(1 if (a and b) else 0)

            elif op == Op.OR:
                b, a = self._pop(), self._pop()
                self._push(1 if (a or b) else 0)

            elif op == Op.NOT:
                a = self._pop()
                self._push(1 if not a else 0)

            elif op == Op.STORE:
                val = self._pop()
                self.memory[arg] = val

            elif op == Op.LOAD:
                if arg not in self.memory:
                    raise VMError(f"Memory address '{arg}' not initialized 📂❌", ip)
                self._push(self.memory[arg])

            elif op == Op.CALL:
                self.call_stack.append((func_name, next_ip))
                self._exec_function(arg)
                if self.halted:
                    return
                if self.call_stack:
                    func_name, next_ip = self.call_stack.pop()
                    func = self.program.functions[func_name]

            elif op == Op.RET:
                return

            elif op == Op.INPUT:
                try:
                    val = input()
                    self._push(val)
                except EOFError:
                    self._push("")

            elif op == Op.INPUT_NUM:
                try:
                    val = input()
                    self._push(int(val))
                except (EOFError, ValueError):
                    self._push(0)

            elif op == Op.HALT:
                self.halted = True
                return

            elif op == Op.NOP:
                pass

            ip = next_ip
