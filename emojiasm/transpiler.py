"""Python-to-EmojiASM transpiler.

Compiles a subset of Python to EmojiASM Program objects via the ast module.
The output feeds directly into the VM, GPU pipeline, C compiler, or disassembler.

Supported Python subset:
- Integer/float literals, True/False
- Variables (assignment, augmented assignment, read)
- Arithmetic: +, -, *, /, //, %
- Comparisons: ==, !=, <, >, <=, >=
- Boolean: and, or, not
- if/elif/else, while, for-range, break
- Function definitions and calls
- print(), random.random()
"""

from __future__ import annotations

import ast
from .opcodes import Op
from .parser import Program, Function, Instruction
from .disasm import disassemble


class TranspileError(Exception):
    """Raised when Python source cannot be transpiled to EmojiASM."""

    def __init__(self, message: str, lineno: int = 0):
        self.lineno = lineno
        loc = f" (line {lineno})" if lineno else ""
        super().__init__(f"TranspileError{loc}: {message}")


# Emoji pool for variable memory cells (50 characters)
EMOJI_POOL = list(
    "🔢📊🎯⭐🌟💎🔥🌊🌈🍎"
    "🍊🍋🍇🍓🍒🥝🥑🌽🥕🍄"
    "🐱🐶🐸🦊🐻🐼🐨🐯🦁🐮"
    "🐷🐵🐔🐧🦅🦆🦉🐝🐛🦋"
    "🌻🌺🌸🌼🌹🍀🌿🌴🌵🎄"
)

# Emoji pool for function names
FUNC_EMOJI_POOL = list(
    "🔲🔳🟥🟦🟩🟨🟧🟪🟫⬛"
    "⬜❤️💙💚💛🧡💜🤎🖤🤍"
)

# Operator mappings
_BINOP_MAP = {
    ast.Add: Op.ADD,
    ast.Sub: Op.SUB,
    ast.Mult: Op.MUL,
    ast.FloorDiv: Op.DIV,
    ast.Mod: Op.MOD,
    ast.Pow: Op.POW,
}

_AUGOP_MAP = {
    ast.Add: Op.ADD,
    ast.Sub: Op.SUB,
    ast.Mult: Op.MUL,
    ast.FloorDiv: Op.DIV,
    ast.Mod: Op.MOD,
    ast.Pow: Op.POW,
    ast.Div: None,  # special handling
}

_UNSUPPORTED_SYNTAX = {
    "ListComp": "List comprehensions not supported. Use a for loop.",
    "SetComp": "Set comprehensions not supported. Use a for loop.",
    "DictComp": "Dict comprehensions not supported.",
    "GeneratorExp": "Generator expressions not supported. Use a for loop.",
    "ClassDef": "Classes not supported.",
    "Try": "Try/except not supported.",
    "TryStar": "Try/except* not supported.",
    "ExceptHandler": "Try/except not supported.",
    "Lambda": "Lambda not supported. Use def.",
    "Yield": "Generators not supported.",
    "YieldFrom": "Generators not supported.",
    "AsyncFunctionDef": "Async not supported.",
    "AsyncFor": "Async not supported.",
    "AsyncWith": "Async not supported.",
    "Await": "Async not supported.",
    "FormattedValue": "f-strings not supported. Use print().",
    "JoinedStr": "f-strings not supported. Use print().",
    "With": "Context managers not supported.",
    "Raise": "Raise not supported.",
    "Assert": "Assert not supported.",
    "Delete": "Delete not supported.",
    "Global": "Global not supported.",
    "Nonlocal": "Nonlocal not supported.",
    "Starred": "Star expressions not supported.",
}


class VarManager:
    """Maps Python variable names to emoji memory cells."""

    def __init__(self):
        self._vars: dict[str, str] = {}  # name -> emoji
        self._next_idx = 0
        self._array_vars: set[str] = set()  # names that are arrays
        self._types: dict[str, str] = {}  # name -> "int", "float", or "unknown"

    def assign(self, name: str) -> str:
        if name not in self._vars:
            if self._next_idx >= len(EMOJI_POOL):
                raise TranspileError(
                    f"Too many variables (max {len(EMOJI_POOL)})"
                )
            self._vars[name] = EMOJI_POOL[self._next_idx]
            self._next_idx += 1
        return self._vars[name]

    def lookup(self, name: str) -> str | None:
        return self._vars.get(name)

    def is_assigned(self, name: str) -> bool:
        return name in self._vars

    def mark_array(self, name: str) -> None:
        self._array_vars.add(name)

    def is_array(self, name: str) -> bool:
        return name in self._array_vars

    def set_type(self, name: str, typ: str) -> None:
        """Record the inferred type of a variable: 'int', 'float', or 'unknown'."""
        self._types[name] = typ

    def get_type(self, name: str) -> str:
        """Return inferred type of a variable, defaulting to 'unknown'."""
        return self._types.get(name, "unknown")


class LabelGenerator:
    """Generates unique label names for control flow."""

    def __init__(self):
        self._counter = 0

    def next(self, prefix: str = "L") -> str:
        self._counter += 1
        return f"{prefix}{self._counter}"


class PythonTranspiler(ast.NodeVisitor):
    """AST visitor that compiles Python to EmojiASM Program."""

    def __init__(self):
        self.program = Program()
        self._current_func: Function | None = None
        self._vars = VarManager()
        self._labels = LabelGenerator()
        self._loop_stack: list[tuple[str, str]] = []  # (loop_label, end_label)
        self._imports: set[str] = set()
        self._func_map: dict[str, str] = {}  # python name -> emoji name
        self._func_idx = 0

    def _emit(self, op: Op, arg=None, node=None):
        lineno = getattr(node, "lineno", 0) if node else 0
        src = ""
        self._current_func.instructions.append(
            Instruction(op=op, arg=arg, line_num=lineno, source=src)
        )

    def _set_label(self, name: str):
        self._current_func.labels[name] = len(
            self._current_func.instructions
        )

    def _alloc_func_emoji(self, name: str) -> str:
        if name in self._func_map:
            return self._func_map[name]
        if self._func_idx >= len(FUNC_EMOJI_POOL):
            raise TranspileError(f"Too many functions (max {len(FUNC_EMOJI_POOL)})")
        emoji = FUNC_EMOJI_POOL[self._func_idx]
        self._func_map[name] = emoji
        self._func_idx += 1
        return emoji

    # ── Type inference ────────────────────────────────────────────────────

    # Math functions that always produce float results
    _FLOAT_PRODUCING_FUNCS = {"sqrt", "sin", "cos", "exp", "log"}

    def _expr_type(self, node: ast.expr) -> str:
        """Infer the type of an expression: 'int', 'float', or 'unknown'."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, float):
                return "float"
            if isinstance(node.value, int) and not isinstance(node.value, bool):
                return "int"
            return "unknown"

        if isinstance(node, ast.Name):
            return self._vars.get_type(node.id)

        if isinstance(node, ast.BinOp):
            lt = self._expr_type(node.left)
            rt = self._expr_type(node.right)
            # True division always produces float
            if isinstance(node.op, ast.Div):
                return "float"
            # If either operand is float, result is float
            if lt == "float" or rt == "float":
                return "float"
            # If both are int, result is int (for +, -, *, //, %, **)
            if lt == "int" and rt == "int":
                return "int"
            return "unknown"

        if isinstance(node, ast.UnaryOp):
            return self._expr_type(node.operand)

        if isinstance(node, ast.Call):
            # math.sqrt, math.sin, etc. always produce float
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "math"
                and node.func.attr in self._FLOAT_PRODUCING_FUNCS
            ):
                return "float"
            # random.random(), random.uniform(), random.gauss() -> float
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "random"
                and node.func.attr in ("random", "uniform", "gauss")
            ):
                return "float"
            # from random import random
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "random"
                and "_from_random_random" in self._imports
            ):
                return "float"
            return "unknown"

        if isinstance(node, ast.Attribute):
            # math.pi, math.e -> float
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "math"
                and node.attr in ("pi", "e")
            ):
                return "float"

        return "unknown"

    # ── Module ───────────────────────────────────────────────────────────

    def visit_Module(self, node: ast.Module):
        # Pre-scan for function definitions to support forward references
        for stmt in node.body:
            if isinstance(stmt, ast.FunctionDef):
                self._alloc_func_emoji(stmt.name)

        # Create main function
        main = Function(name="🏠")
        self.program.functions["🏠"] = main
        self._current_func = main

        # Compile top-level statements (skip function defs, compile them separately)
        for stmt in node.body:
            if isinstance(stmt, ast.FunctionDef):
                continue
            self.visit(stmt)

        self._emit(Op.HALT)

        # Now compile function definitions
        saved_func = self._current_func
        saved_vars = self._vars

        for stmt in node.body:
            if isinstance(stmt, ast.FunctionDef):
                self._compile_function_def(stmt)

        self._current_func = saved_func
        self._vars = saved_vars

    # ── Statements ───────────────────────────────────────────────────────

    def visit_Expr(self, node: ast.Expr):
        self.visit(node.value)

    def _is_array_alloc(self, node: ast.expr):
        """Detect [fill] * N or N * [fill] pattern for array allocation.

        Returns (fill_value, size) if matched, else None.
        """
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Mult):
            return None
        # [fill] * N
        if (
            isinstance(node.left, ast.List)
            and len(node.left.elts) == 1
            and isinstance(node.left.elts[0], ast.Constant)
            and isinstance(node.right, ast.Constant)
            and isinstance(node.right.value, (int, float))
        ):
            return (node.left.elts[0].value, node.right.value)
        # N * [fill]
        if (
            isinstance(node.right, ast.List)
            and len(node.right.elts) == 1
            and isinstance(node.right.elts[0], ast.Constant)
            and isinstance(node.left, ast.Constant)
            and isinstance(node.left.value, (int, float))
        ):
            return (node.right.elts[0].value, node.left.value)
        return None

    def visit_Assign(self, node: ast.Assign):
        targets = node.targets

        # Single target: check for subscript assignment (arr[i] = val)
        if len(targets) == 1 and isinstance(targets[0], ast.Subscript):
            sub = targets[0]
            if not isinstance(sub.value, ast.Name):
                raise TranspileError(
                    "Only simple variable subscript assignment supported",
                    node.lineno,
                )
            var_name = sub.value.id
            cell = self._vars.lookup(var_name)
            if cell is None or not self._vars.is_array(var_name):
                raise TranspileError(
                    f"Variable '{var_name}' is not a known array",
                    node.lineno,
                )
            # Stack order for ASTORE: index first, then value on top
            self.visit(sub.slice)   # push index
            self.visit(node.value)  # push value
            self._emit(Op.ASTORE, cell, node=node)
            return

        # Check for array allocation pattern: arr = [0.0] * N
        alloc = self._is_array_alloc(node.value)
        if alloc is not None:
            _fill, size = alloc
            for i, target in enumerate(targets):
                if not isinstance(target, ast.Name):
                    raise TranspileError(
                        "Only simple variable assignment supported for array allocation",
                        node.lineno,
                    )
                cell = self._vars.assign(target.id)
                self._vars.mark_array(target.id)
                self._emit(Op.PUSH, int(size), node=node)
                self._emit(Op.ALLOC, cell, node=node)
            return

        # Normal scalar assignment
        val_type = self._expr_type(node.value)
        self.visit(node.value)
        for i, target in enumerate(targets):
            if not isinstance(target, ast.Name):
                raise TranspileError(
                    f"Only simple variable assignment supported",
                    node.lineno,
                )
            cell = self._vars.assign(target.id)
            self._vars.set_type(target.id, val_type)
            if i < len(targets) - 1:
                self._emit(Op.DUP, node=node)
            self._emit(Op.STORE, cell, node=node)

    def visit_AugAssign(self, node: ast.AugAssign):
        # Subscript augmented assignment: arr[i] += val
        if isinstance(node.target, ast.Subscript):
            sub = node.target
            if not isinstance(sub.value, ast.Name):
                raise TranspileError(
                    "Only simple variable subscript augmented assignment supported",
                    node.lineno,
                )
            var_name = sub.value.id
            cell = self._vars.lookup(var_name)
            if cell is None or not self._vars.is_array(var_name):
                raise TranspileError(
                    f"Variable '{var_name}' is not a known array",
                    node.lineno,
                )
            # Stack: push index, DUP (save index), ALOAD (load current), visit value, OP
            # Then need: index, new_value for ASTORE
            self.visit(sub.slice)            # push index
            self._emit(Op.DUP, node=node)    # save index copy
            self._emit(Op.ALOAD, cell, node=node)  # load arr[i] (consumes one index copy)

            if isinstance(node.op, ast.Div):
                self._emit(Op.PUSH, 1.0, node=node)
                self._emit(Op.MUL, node=node)
                self.visit(node.value)
                self._emit(Op.DIV, node=node)
            else:
                op = _AUGOP_MAP.get(type(node.op))
                if op is None:
                    raise TranspileError(
                        f"Unsupported augmented assignment operator: {type(node.op).__name__}",
                        node.lineno,
                    )
                self.visit(node.value)
                self._emit(op, node=node)

            # Stack now: [saved_index, new_value]
            # ASTORE expects: index first, value on top — which is what we have
            self._emit(Op.ASTORE, cell, node=node)
            return

        if not isinstance(node.target, ast.Name):
            raise TranspileError(
                "Only simple variable augmented assignment supported",
                node.lineno,
            )
        cell = self._vars.lookup(node.target.id)
        if cell is None:
            raise TranspileError(
                f"Variable '{node.target.id}' used before assignment",
                node.lineno,
            )
        self._emit(Op.LOAD, cell, node=node)

        if isinstance(node.op, ast.Div):
            # True division: coerce to float (skip if var is already float)
            if self._vars.get_type(node.target.id) != "float":
                self._emit(Op.PUSH, 1.0, node=node)
                self._emit(Op.MUL, node=node)
            self.visit(node.value)
            self._emit(Op.DIV, node=node)
        else:
            op = _AUGOP_MAP.get(type(node.op))
            if op is None:
                raise TranspileError(
                    f"Unsupported augmented assignment operator: {type(node.op).__name__}",
                    node.lineno,
                )
            self.visit(node.value)
            self._emit(op, node=node)

        self._emit(Op.STORE, cell, node=node)

        # Update type tracking for augmented assignment
        if isinstance(node.op, ast.Div):
            self._vars.set_type(node.target.id, "float")
        else:
            cur_type = self._vars.get_type(node.target.id)
            val_type = self._expr_type(node.value)
            if cur_type == "float" or val_type == "float":
                self._vars.set_type(node.target.id, "float")

    def visit_If(self, node: ast.If):
        if not node.orelse:
            # if-only
            end_label = self._labels.next("if_end")
            self.visit(node.test)
            self._emit(Op.JZ, end_label, node=node)
            for stmt in node.body:
                self.visit(stmt)
            self._set_label(end_label)
        else:
            # if-else or if-elif-else
            else_label = self._labels.next("if_else")
            end_label = self._labels.next("if_end")
            self.visit(node.test)
            self._emit(Op.JZ, else_label, node=node)
            for stmt in node.body:
                self.visit(stmt)
            self._emit(Op.JMP, end_label, node=node)
            self._set_label(else_label)
            for stmt in node.orelse:
                self.visit(stmt)
            self._set_label(end_label)

    def visit_While(self, node: ast.While):
        loop_label = self._labels.next("while_start")
        end_label = self._labels.next("while_end")

        self._set_label(loop_label)
        self.visit(node.test)
        self._emit(Op.JZ, end_label, node=node)

        self._loop_stack.append((loop_label, end_label))
        for stmt in node.body:
            self.visit(stmt)
        self._loop_stack.pop()

        self._emit(Op.JMP, loop_label, node=node)
        self._set_label(end_label)

    def visit_For(self, node: ast.For):
        if not isinstance(node.target, ast.Name):
            raise TranspileError(
                "Only simple variable names supported as for-loop target",
                node.lineno,
            )
        if not (
            isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id == "range"
        ):
            raise TranspileError(
                "Only 'for x in range(...)' loops are supported",
                node.lineno,
            )

        args = node.iter.args
        if len(args) == 1:
            start_node, stop_node, step_val = None, args[0], 1
        elif len(args) == 2:
            start_node, stop_node, step_val = args[0], args[1], 1
        elif len(args) == 3:
            start_node, stop_node = args[0], args[1]
            # Step must be a constant for now
            if isinstance(args[2], ast.Constant) and isinstance(args[2].value, (int, float)):
                step_val = args[2].value
            elif isinstance(args[2], ast.UnaryOp) and isinstance(args[2].op, ast.USub) and isinstance(args[2].operand, ast.Constant):
                step_val = -args[2].operand.value
            else:
                # Non-constant step: compile as expression
                step_val = None
        else:
            raise TranspileError(
                f"range() takes 1 to 3 arguments, got {len(args)}",
                node.lineno,
            )

        iter_cell = self._vars.assign(node.target.id)
        loop_label = self._labels.next("for_start")
        end_label = self._labels.next("for_end")

        # Initialize iterator
        if start_node is not None:
            self.visit(start_node)
        else:
            self._emit(Op.PUSH, 0, node=node)
        self._emit(Op.STORE, iter_cell, node=node)

        # Loop header
        self._set_label(loop_label)
        self._emit(Op.LOAD, iter_cell, node=node)
        self.visit(stop_node)

        # Comparison: for positive step use CMP_LT, for negative use CMP_GT
        if step_val is not None and step_val < 0:
            self._emit(Op.CMP_GT, node=node)
        else:
            self._emit(Op.CMP_LT, node=node)
        self._emit(Op.JZ, end_label, node=node)

        # Body
        self._loop_stack.append((loop_label, end_label))
        for stmt in node.body:
            self.visit(stmt)
        self._loop_stack.pop()

        # Increment
        self._emit(Op.LOAD, iter_cell, node=node)
        if step_val is not None:
            self._emit(Op.PUSH, step_val, node=node)
        else:
            self.visit(args[2])
        self._emit(Op.ADD, node=node)
        self._emit(Op.STORE, iter_cell, node=node)
        self._emit(Op.JMP, loop_label, node=node)

        self._set_label(end_label)

    def visit_Break(self, node: ast.Break):
        if not self._loop_stack:
            raise TranspileError("'break' outside loop", node.lineno)
        _, end_label = self._loop_stack[-1]
        self._emit(Op.JMP, end_label, node=node)

    def visit_Continue(self, node: ast.Continue):
        if not self._loop_stack:
            raise TranspileError("'continue' outside loop", node.lineno)
        loop_label, _ = self._loop_stack[-1]
        self._emit(Op.JMP, loop_label, node=node)

    def visit_Pass(self, node: ast.Pass):
        self._emit(Op.NOP, node=node)

    def visit_Return(self, node: ast.Return):
        if node.value is not None:
            self.visit(node.value)
        self._emit(Op.RET, node=node)

    def visit_Import(self, node: ast.Import):
        allowed = {"random", "math"}
        for alias in node.names:
            if alias.name not in allowed:
                raise TranspileError(
                    f"Unsupported import: '{alias.name}'. Only {allowed} are supported.",
                    node.lineno,
                )
            self._imports.add(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        allowed = {"random", "math"}
        if node.module not in allowed:
            raise TranspileError(
                f"Unsupported import: '{node.module}'. Only {allowed} are supported.",
                node.lineno,
            )
        self._imports.add(node.module)
        for alias in node.names:
            name = alias.asname or alias.name
            if node.module == "random" and alias.name == "random":
                self._imports.add("_from_random_random")
            elif node.module == "random" and alias.name == "randint":
                pass  # not supported yet but don't block import

    # ── Expressions ──────────────────────────────────────────────────────

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, bool):
            self._emit(Op.PUSH, 1 if node.value else 0, node=node)
        elif isinstance(node.value, (int, float)):
            self._emit(Op.PUSH, node.value, node=node)
        elif isinstance(node.value, str):
            raise TranspileError(
                "String literals not supported in expressions. Use print() for output.",
                node.lineno,
            )
        elif node.value is None:
            raise TranspileError(
                "None is not supported.",
                node.lineno,
            )
        else:
            raise TranspileError(
                f"Unsupported constant type: {type(node.value).__name__}",
                node.lineno,
            )

    def visit_Name(self, node: ast.Name):
        # Check if it's a builtin
        if node.id in ("True",):
            self._emit(Op.PUSH, 1, node=node)
            return
        if node.id in ("False",):
            self._emit(Op.PUSH, 0, node=node)
            return

        cell = self._vars.lookup(node.id)
        if cell is None:
            # Could be a function name or module name - allow
            if node.id in self._func_map or node.id in self._imports:
                return  # handled by visit_Call / visit_Attribute
            raise TranspileError(
                f"Variable '{node.id}' used before assignment",
                node.lineno,
            )
        self._emit(Op.LOAD, cell, node=node)

    def visit_BinOp(self, node: ast.BinOp):
        # ── Constant folding ────────────────────────────────────────────
        # If both sides are numeric constants, evaluate at compile time.
        if (
            isinstance(node.left, ast.Constant)
            and isinstance(node.right, ast.Constant)
            and isinstance(node.left.value, (int, float))
            and isinstance(node.right.value, (int, float))
        ):
            lv, rv = node.left.value, node.right.value
            _FOLD_OPS = {
                ast.Add: lambda a, b: a + b,
                ast.Sub: lambda a, b: a - b,
                ast.Mult: lambda a, b: a * b,
                ast.Div: lambda a, b: a / b,
                ast.FloorDiv: lambda a, b: a // b,
                ast.Mod: lambda a, b: a % b,
                ast.Pow: lambda a, b: a ** b,
            }
            fold_fn = _FOLD_OPS.get(type(node.op))
            if fold_fn is not None:
                # Guard: don't fold division by zero
                if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and rv == 0:
                    pass  # fall through to runtime
                else:
                    try:
                        result = fold_fn(lv, rv)
                        # Guard: don't fold if result is not finite
                        if isinstance(result, float) and (
                            result != result  # NaN
                            or result == float("inf")
                            or result == float("-inf")
                        ):
                            pass  # fall through to runtime
                        else:
                            self._emit(Op.PUSH, result, node=node)
                            return
                    except (ArithmeticError, ValueError, OverflowError):
                        pass  # fall through to runtime

        # ── Identity elimination ────────────────────────────────────────
        # x + 0, 0 + x -> x
        if isinstance(node.op, ast.Add):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self.visit(node.left)
                return
            if isinstance(node.left, ast.Constant) and node.left.value == 0:
                self.visit(node.right)
                return
        # x - 0 -> x
        if isinstance(node.op, ast.Sub):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self.visit(node.left)
                return
        # x * 1, 1 * x -> x
        if isinstance(node.op, ast.Mult):
            if isinstance(node.right, ast.Constant) and node.right.value == 1:
                self.visit(node.left)
                return
            if isinstance(node.left, ast.Constant) and node.left.value == 1:
                self.visit(node.right)
                return
            # x * 0, 0 * x -> 0 (skip visiting x to avoid side effects)
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self._emit(Op.PUSH, 0, node=node)
                return
            if isinstance(node.left, ast.Constant) and node.left.value == 0:
                self._emit(Op.PUSH, 0, node=node)
                return
        # x / 1 -> x (true division still needs float coercion unless already float)
        if isinstance(node.op, ast.Div):
            if isinstance(node.right, ast.Constant) and node.right.value == 1:
                self.visit(node.left)
                # Skip coercion if left is already known float
                if self._expr_type(node.left) != "float":
                    self._emit(Op.PUSH, 1.0, node=node)
                    self._emit(Op.MUL, node=node)
                return
        # x // 1 -> x
        if isinstance(node.op, ast.FloorDiv):
            if isinstance(node.right, ast.Constant) and node.right.value == 1:
                self.visit(node.left)
                return

        # ── Normal code generation ──────────────────────────────────────
        if isinstance(node.op, ast.Div):
            # True division: coerce left to float (skip if already float)
            self.visit(node.left)
            if self._expr_type(node.left) != "float":
                self._emit(Op.PUSH, 1.0, node=node)
                self._emit(Op.MUL, node=node)
            self.visit(node.right)
            self._emit(Op.DIV, node=node)
            return

        op = _BINOP_MAP.get(type(node.op))
        if op is None:
            raise TranspileError(
                f"Unsupported operator: {type(node.op).__name__}",
                node.lineno,
            )

        self.visit(node.left)
        self.visit(node.right)
        self._emit(op, node=node)

    def visit_UnaryOp(self, node: ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            self._emit(Op.PUSH, 0, node=node)
            self.visit(node.operand)
            self._emit(Op.SUB, node=node)
        elif isinstance(node.op, ast.UAdd):
            self.visit(node.operand)
        elif isinstance(node.op, ast.Not):
            self.visit(node.operand)
            self._emit(Op.NOT, node=node)
        else:
            raise TranspileError(
                f"Unsupported unary operator: {type(node.op).__name__}",
                node.lineno,
            )

    def _emit_cmp_op(self, cmp_op, node):
        """Emit comparison opcodes for a single comparison operator."""
        if isinstance(cmp_op, ast.Eq):
            self._emit(Op.CMP_EQ, node=node)
        elif isinstance(cmp_op, ast.NotEq):
            self._emit(Op.CMP_EQ, node=node)
            self._emit(Op.NOT, node=node)
        elif isinstance(cmp_op, ast.Lt):
            self._emit(Op.CMP_LT, node=node)
        elif isinstance(cmp_op, ast.Gt):
            self._emit(Op.CMP_GT, node=node)
        elif isinstance(cmp_op, ast.LtE):
            self._emit(Op.CMP_GT, node=node)
            self._emit(Op.NOT, node=node)
        elif isinstance(cmp_op, ast.GtE):
            self._emit(Op.CMP_LT, node=node)
            self._emit(Op.NOT, node=node)
        else:
            raise TranspileError(
                f"Unsupported comparison: {type(cmp_op).__name__}",
                node.lineno,
            )

    def visit_Compare(self, node: ast.Compare):
        n = len(node.ops)
        self.visit(node.left)

        for i, (cmp_op, comparator) in enumerate(
            zip(node.ops, node.comparators)
        ):
            is_last = i == n - 1

            self.visit(comparator)

            if not is_last:
                # Save comparator for next comparison:
                # stack: [..., left_val, comp] -> DUP -> [..., left_val, comp, comp_copy]
                # ROT -> [..., comp, comp_copy, left_val]
                # SWAP -> [..., comp, left_val, comp_copy]
                # Now CMP will consume left_val and comp_copy correctly
                self._emit(Op.DUP, node=node)
                self._emit(Op.ROT, node=node)
                self._emit(Op.SWAP, node=node)

            self._emit_cmp_op(cmp_op, node)

            if i > 0 and not is_last:
                # Combine with previous result: stack is [prev_result, saved_comp, cmp_result]
                # ROT -> [saved_comp, cmp_result, prev_result]
                # AND -> [saved_comp, combined]
                # SWAP -> [combined, saved_comp]
                self._emit(Op.ROT, node=node)
                self._emit(Op.AND, node=node)
                self._emit(Op.SWAP, node=node)
            elif i > 0 and is_last:
                # Last comparison, combine with accumulated result
                # stack: [accumulated, cmp_result] -> AND -> [final]
                self._emit(Op.AND, node=node)
            elif not is_last:
                # First comparison (i==0), not last: swap result below saved comparator
                # stack: [saved_comp, cmp_result] -> SWAP -> [cmp_result, saved_comp]
                self._emit(Op.SWAP, node=node)

    def visit_BoolOp(self, node: ast.BoolOp):
        self.visit(node.values[0])
        for val in node.values[1:]:
            self.visit(val)
            if isinstance(node.op, ast.And):
                self._emit(Op.AND, node=node)
            elif isinstance(node.op, ast.Or):
                self._emit(Op.OR, node=node)

    def visit_Call(self, node: ast.Call):
        # print(...)
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            self._compile_print(node)
            return

        # random.random()
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "random"
            and node.func.attr == "random"
        ):
            self._emit(Op.RANDOM, node=node)
            return

        # random.uniform(a, b) -> a + (b - a) * random()
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "random"
            and node.func.attr == "uniform"
        ):
            if "random" not in self._imports:
                raise TranspileError(
                    "random module not imported. Add 'import random'.",
                    node.lineno,
                )
            if len(node.args) != 2:
                raise TranspileError(
                    "random.uniform() takes exactly 2 arguments",
                    node.lineno,
                )
            # Inline: a + (b - a) * random()
            self.visit(node.args[1])       # b
            self.visit(node.args[0])       # a
            self._emit(Op.SUB, node=node)  # b - a
            self._emit(Op.RANDOM, node=node)  # random float [0, 1)
            self._emit(Op.MUL, node=node)  # (b - a) * random
            self.visit(node.args[0])       # a
            self._emit(Op.ADD, node=node)  # a + (b - a) * random
            return

        # random.gauss(mu, sigma) -> Box-Muller transform
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "random"
            and node.func.attr == "gauss"
        ):
            if "random" not in self._imports:
                raise TranspileError(
                    "random module not imported. Add 'import random'.",
                    node.lineno,
                )
            if len(node.args) != 2:
                raise TranspileError(
                    "random.gauss() takes exactly 2 arguments",
                    node.lineno,
                )
            # Box-Muller: mu + sigma * sqrt(-2 * log(u1)) * cos(2 * pi * u2)
            self._emit(Op.RANDOM, node=node)      # u1
            self._emit(Op.LOG, node=node)          # log(u1)
            self._emit(Op.PUSH, -2.0, node=node)   # -2.0
            self._emit(Op.MUL, node=node)          # -2 * log(u1)
            self._emit(Op.SQRT, node=node)         # sqrt(-2 * log(u1))
            self._emit(Op.RANDOM, node=node)       # u2
            self._emit(Op.PUSH, 6.283185307179586, node=node)  # 2*pi
            self._emit(Op.MUL, node=node)          # 2*pi*u2
            self._emit(Op.COS, node=node)          # cos(2*pi*u2)
            self._emit(Op.MUL, node=node)          # z = sqrt(...) * cos(...)
            self.visit(node.args[1])               # sigma
            self._emit(Op.MUL, node=node)          # sigma * z
            self.visit(node.args[0])               # mu
            self._emit(Op.ADD, node=node)          # mu + sigma * z
            return

        # random() from "from random import random"
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "random"
            and "_from_random_random" in self._imports
        ):
            self._emit(Op.RANDOM, node=node)
            return

        # math.* functions
        _MATH_FUNC_MAP = {
            "sqrt": Op.SQRT,
            "sin": Op.SIN,
            "cos": Op.COS,
            "exp": Op.EXP,
            "log": Op.LOG,
        }
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "math"
            and node.func.attr in _MATH_FUNC_MAP
        ):
            if "math" not in self._imports:
                raise TranspileError(
                    "math module not imported. Add 'import math'.",
                    node.lineno,
                )
            if len(node.args) != 1:
                raise TranspileError(
                    f"math.{node.func.attr}() takes exactly 1 argument",
                    node.lineno,
                )
            self.visit(node.args[0])
            self._emit(_MATH_FUNC_MAP[node.func.attr], node=node)
            return

        # abs(x) builtin
        if isinstance(node.func, ast.Name) and node.func.id == "abs":
            if len(node.args) != 1:
                raise TranspileError(
                    "abs() takes exactly 1 argument",
                    node.lineno,
                )
            self.visit(node.args[0])
            self._emit(Op.ABS, node=node)
            return

        # min(a, b) builtin
        if isinstance(node.func, ast.Name) and node.func.id == "min":
            if len(node.args) != 2:
                raise TranspileError(
                    "min() takes exactly 2 arguments",
                    node.lineno,
                )
            self.visit(node.args[0])
            self.visit(node.args[1])
            self._emit(Op.MIN, node=node)
            return

        # max(a, b) builtin
        if isinstance(node.func, ast.Name) and node.func.id == "max":
            if len(node.args) != 2:
                raise TranspileError(
                    "max() takes exactly 2 arguments",
                    node.lineno,
                )
            self.visit(node.args[0])
            self.visit(node.args[1])
            self._emit(Op.MAX, node=node)
            return

        # len(arr) builtin for arrays
        if isinstance(node.func, ast.Name) and node.func.id == "len":
            if len(node.args) != 1:
                raise TranspileError(
                    "len() takes exactly 1 argument",
                    node.lineno,
                )
            arg = node.args[0]
            if isinstance(arg, ast.Name) and self._vars.is_array(arg.id):
                cell = self._vars.lookup(arg.id)
                self._emit(Op.ALEN, cell, node=node)
                return
            raise TranspileError(
                "len() only supported on array variables",
                node.lineno,
            )

        # sum(arr) builtin for arrays — inline accumulation loop
        if isinstance(node.func, ast.Name) and node.func.id == "sum":
            if len(node.args) != 1:
                raise TranspileError(
                    "sum() takes exactly 1 argument",
                    node.lineno,
                )
            arg = node.args[0]
            if isinstance(arg, ast.Name) and self._vars.is_array(arg.id):
                cell = self._vars.lookup(arg.id)
                loop_label = self._labels.next("sum_loop")
                end_label = self._labels.next("sum_end")
                temp_i_cell = self._vars.assign("__sum_i__")

                # Push initial accumulator value
                self._emit(Op.PUSH, 0.0, node=node)
                # Initialize loop counter to 0
                self._emit(Op.PUSH, 0, node=node)
                self._emit(Op.STORE, temp_i_cell, node=node)
                # Loop: while i < len(arr)
                self._set_label(loop_label)
                self._emit(Op.LOAD, temp_i_cell, node=node)
                self._emit(Op.ALEN, cell, node=node)
                self._emit(Op.CMP_LT, node=node)
                self._emit(Op.JZ, end_label, node=node)
                # Load arr[i] and add to accumulator
                self._emit(Op.LOAD, temp_i_cell, node=node)
                self._emit(Op.ALOAD, cell, node=node)
                self._emit(Op.ADD, node=node)
                # i += 1
                self._emit(Op.LOAD, temp_i_cell, node=node)
                self._emit(Op.PUSH, 1, node=node)
                self._emit(Op.ADD, node=node)
                self._emit(Op.STORE, temp_i_cell, node=node)
                self._emit(Op.JMP, loop_label, node=node)
                self._set_label(end_label)
                # Accumulator (sum) is now on top of stack
                return
            raise TranspileError(
                "sum() only supported on array variables",
                node.lineno,
            )

        # User-defined function call
        if isinstance(node.func, ast.Name) and node.func.id in self._func_map:
            emoji = self._func_map[node.func.id]
            # Save/restore local variables around call (memory cells are global,
            # so recursive calls would clobber parent's locals without this)
            local_cells = [
                (n, c) for n, c in self._vars._vars.items()
                if n != "__retval__"
            ]
            # Save: push all locals onto stack
            for _name, cell in local_cells:
                self._emit(Op.LOAD, cell, node=node)
            # Push arguments left to right
            for arg in node.args:
                self.visit(arg)
            self._emit(Op.CALL, emoji, node=node)
            if local_cells:
                # Result is on top of stack, locals underneath
                # Save result to a temp cell, restore locals, then push result back
                temp_cell = self._vars.assign("__retval__")
                self._emit(Op.STORE, temp_cell, node=node)
                # Restore locals (reverse order since stack is LIFO)
                for _name, cell in reversed(local_cells):
                    self._emit(Op.STORE, cell, node=node)
                self._emit(Op.LOAD, temp_cell, node=node)
            return

        # range() - should not be called as expression
        if isinstance(node.func, ast.Name) and node.func.id == "range":
            raise TranspileError(
                "range() can only be used in 'for x in range(...)' loops",
                node.lineno,
            )

        func_name = ast.dump(node.func)
        raise TranspileError(
            f"Unsupported function call: {func_name}",
            node.lineno,
        )

    def visit_Attribute(self, node: ast.Attribute):
        # math.pi and math.e constants
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "math"
            and node.attr in ("pi", "e")
        ):
            if "math" not in self._imports:
                raise TranspileError(
                    "math module not imported. Add 'import math'.",
                    getattr(node, "lineno", 0),
                )
            if node.attr == "pi":
                self._emit(Op.PUSH, 3.141592653589793, node=node)
            elif node.attr == "e":
                self._emit(Op.PUSH, 2.718281828459045, node=node)
            return
        # Allow random.random etc. to be handled by visit_Call
        pass

    def visit_IfExp(self, node: ast.IfExp):
        # Ternary: body if test else orelse
        else_label = self._labels.next("tern_else")
        end_label = self._labels.next("tern_end")
        self.visit(node.test)
        self._emit(Op.JZ, else_label, node=node)
        self.visit(node.body)
        self._emit(Op.JMP, end_label, node=node)
        self._set_label(else_label)
        self.visit(node.orelse)
        self._set_label(end_label)

    def visit_Subscript(self, node: ast.Subscript):
        """Array read: arr[i] -> push index, ALOAD cell."""
        if not isinstance(node.value, ast.Name):
            raise TranspileError(
                "Only simple variable subscript access supported",
                getattr(node, "lineno", 0),
            )
        var_name = node.value.id
        cell = self._vars.lookup(var_name)
        if cell is None or not self._vars.is_array(var_name):
            raise TranspileError(
                f"Variable '{var_name}' is not a known array",
                getattr(node, "lineno", 0),
            )
        self.visit(node.slice)  # push index
        self._emit(Op.ALOAD, cell, node=node)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _compile_print(self, node: ast.Call):
        """Compile a print() call."""
        # Check for end="" keyword
        use_println = True
        for kw in node.keywords:
            if kw.arg == "end":
                if isinstance(kw.value, ast.Constant) and kw.value.value == "":
                    use_println = False

        args = node.args
        if not args:
            # print() with no args -> just a newline
            self._emit(Op.PUSH, 0, node=node)
            self._emit(Op.PRINTS, "", node=node)
            self._emit(Op.PRINTLN, node=node)
            return

        if len(args) == 1:
            self.visit(args[0])
            self._emit(Op.PRINTLN if use_println else Op.PRINT, node=node)
            return

        # Multiple args: print(a, b, c) -> a " " b " " c \n
        for i, arg in enumerate(args):
            self.visit(arg)
            if i < len(args) - 1:
                self._emit(Op.PRINT, node=node)
                self._emit(Op.PRINTS, " ", node=node)
                self._emit(Op.PRINT, node=node)
            else:
                self._emit(Op.PRINTLN if use_println else Op.PRINT, node=node)

    def _compile_function_def(self, node: ast.FunctionDef):
        """Compile a function definition into a separate EmojiASM function."""
        emoji = self._func_map[node.name]
        func = Function(name=emoji)
        self.program.functions[emoji] = func

        saved_func = self._current_func
        saved_vars = self._vars
        self._current_func = func
        self._vars = VarManager()

        # Parameters: stored in reverse order since stack is LIFO
        # When called, args are pushed left-to-right, so rightmost is on top
        params = [p.arg for p in node.args.args]
        for param in reversed(params):
            cell = self._vars.assign(param)
            self._emit(Op.STORE, cell, node=node)

        # Compile body
        for stmt in node.body:
            self.visit(stmt)

        # Ensure function ends with RET
        if not func.instructions or func.instructions[-1].op != Op.RET:
            self._emit(Op.RET, node=node)

        self._current_func = saved_func
        self._vars = saved_vars

    def generic_visit(self, node: ast.AST):
        node_type = type(node).__name__
        hint = _UNSUPPORTED_SYNTAX.get(node_type)
        if hint:
            lineno = getattr(node, "lineno", 0)
            raise TranspileError(hint, lineno)
        # For truly unknown nodes, try visiting children
        # (this handles things like ast.Load, ast.Store, etc.)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.AST) and hasattr(child, "lineno"):
                # Only visit "significant" child nodes
                pass
        # Don't raise for internal AST nodes like Load, Store, Del, etc.


# ── Module-level API ─────────────────────────────────────────────────────

def transpile(source: str) -> Program:
    """Transpile Python source code to an EmojiASM Program.

    The returned Program can be passed directly to:
    - VM(program).run() for CPU execution
    - compile_to_bytecode(program) for GPU execution
    - compile_to_c(program) for native compilation
    - disassemble(program) for EmojiASM source text
    """
    if not source or not source.strip():
        raise TranspileError("Empty source")

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise TranspileError(
            f"Python syntax error: {e.msg}", e.lineno or 0
        ) from e

    compiler = PythonTranspiler()
    compiler.visit_Module(tree)
    return compiler.program


def transpile_to_source(source: str) -> str:
    """Transpile Python source to EmojiASM source text.

    Convenience function that transpiles and then disassembles.
    """
    program = transpile(source)
    return disassemble(program)
