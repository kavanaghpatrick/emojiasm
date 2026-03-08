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

# Maps common unsupported patterns to actionable suggestions
_SUGGESTION_MAP: dict[str, str] = {
    # Unsupported function calls -> closest supported alternative
    "int": "Use `x // 1` for integer conversion",
    "float": "Use `x * 1.0` for float conversion",
    "round": "Use `int(x + 0.5)` or `x // 1` for rounding",
    "str": "String conversion not supported; use print() for output",
    "input": "Interactive input not supported; use variable assignment instead",
    "type": "Type checking not supported at runtime",
    "isinstance": "Type checking not supported at runtime",
    "enumerate": "Use `for i in range(len(arr))` with `arr[i]` instead of enumerate()",
    "zip": "Use index-based loops instead of zip()",
    "map": "Use a for loop instead of map()",
    "filter": "Use a for loop with if instead of filter()",
    "sorted": "Sorting not supported; use manual comparison loops",
    "reversed": "Use `for i in range(N-1, -1, -1)` instead of reversed()",
    "list": "Use `arr = [0.0] * N` for fixed-size arrays",
    "dict": "Dictionaries not supported; use arrays with index mapping",
    "set": "Sets not supported; use arrays",
    "tuple": "Tuples not supported; use separate variables",
    "open": "File I/O not supported",
    "pow": "Use `x ** y` or `math.exp(y * math.log(x))` instead of pow()",
    "math.floor": "Use `x // 1` for floor",
    "math.ceil": "Use `-((-x) // 1)` for ceil",
    "math.pow": "Use `x ** y` operator instead of math.pow()",
    "math.fabs": "Use `abs(x)` instead of math.fabs()",
    "random.randint": "Use `int(random.uniform(a, b+1))` instead of randint()",
    "random.choice": "Use `arr[int(random.random() * len(arr))]` instead of choice()",
    "random.shuffle": "Shuffling not supported; use Fisher-Yates with random.random()",
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


# ── Numpy shim AST rewriter ──────────────────────────────────────────────


class NumpyShim(ast.NodeTransformer):
    """Rewrite numpy API calls in a Python AST to stdlib equivalents.

    EmojiASM does not support numpy, but many LLM-generated programs use it
    for simple math and random operations.  This transformer detects
    ``import numpy as np`` (or ``import numpy``, or any alias) and rewrites
    the supported subset of numpy calls to their ``random`` / ``math`` /
    builtin equivalents so the transpiler can handle them.

    **Supported rewrites:**

    =====================  ============================
    numpy call             stdlib replacement
    =====================  ============================
    np.random.random()     random.random()
    np.random.normal(m,s)  random.gauss(m,s)
    np.random.uniform(a,b) random.uniform(a,b)
    np.sqrt(x)             math.sqrt(x)
    np.sin(x)              math.sin(x)
    np.cos(x)              math.cos(x)
    np.exp(x)              math.exp(x)
    np.log(x)              math.log(x)
    np.abs(x)              abs(x)
    np.pi                  math.pi
    np.e                   math.e
    =====================  ============================

    **Unsupported (raises TranspileError):**

    - ``from numpy import *`` — ambiguous scope
    - ``np.array()``, ``np.zeros()``, ``np.ones()`` — use ``[0.0] * N``
    - ``np.linalg.*`` — not available

    Usage::

        shim = NumpyShim(tree)
        tree = shim.apply()
    """

    # ── Mapping tables ────────────────────────────────────────────────

    # np.<func>(x) -> (module | None, function_name)
    # None means builtin (no module prefix).
    FUNC_REWRITES: dict[str, tuple[str | None, str]] = {
        "sqrt": ("math", "sqrt"),
        "sin": ("math", "sin"),
        "cos": ("math", "cos"),
        "exp": ("math", "exp"),
        "log": ("math", "log"),
        "abs": (None, "abs"),  # builtin
    }

    # np.random.<func> -> random.<func>
    RANDOM_REWRITES: dict[str, str] = {
        "random": "random",
        "normal": "gauss",
        "uniform": "uniform",
    }

    # np.<constant> -> math.<constant>
    CONST_REWRITES: dict[str, str] = {
        "pi": "pi",
        "e": "e",
    }

    # np.<unsupported>() — raise helpful errors
    _UNSUPPORTED_FUNCS: dict[str, str] = {
        "array": "Use `arr = [0.0] * N` for fixed-size arrays",
        "zeros": "Use `arr = [0.0] * N` for zero-initialized arrays",
        "ones": "Use `arr = [1.0] * N` for one-initialized arrays",
        "arange": "Use `for i in range(N)` instead of np.arange()",
        "linspace": "Use a for-loop with manual step calculation",
        "mean": "Use `sum(values) / len(values)` instead",
        "sum": "Use builtin `sum()` or a for-loop accumulator",
    }

    # np.linalg.* and np.fft.* — entire submodules unsupported
    _UNSUPPORTED_SUBMODULES: set[str] = {"linalg", "fft", "ma", "polynomial"}

    def __init__(self, tree: ast.Module) -> None:
        """Initialize the shim with a parsed AST.

        Args:
            tree: The parsed AST module to transform.

        Raises:
            TranspileError: If ``from numpy import *`` is detected.
        """
        self._tree = tree
        self._alias: str | None = None
        self._existing_imports: set[str] = set()

    def apply(self) -> ast.Module:
        """Run all three passes and return the transformed AST.

        Returns:
            The rewritten AST with numpy calls replaced by stdlib calls.
            If no numpy import is found, returns the tree unchanged.
        """
        self._scan_imports()
        if self._alias is None:
            return self._tree

        # Rewrite AST nodes (visit_Call / visit_Attribute)
        self._tree = self.visit(self._tree)

        # Replace numpy import with random + math
        self._replace_imports()

        ast.fix_missing_locations(self._tree)
        return self._tree

    # ── Pass 1: import scanning ───────────────────────────────────────

    def _scan_imports(self) -> None:
        """Scan top-level imports to find the numpy alias and existing imports.

        Detects all import styles:
        - ``import numpy`` -> alias = "numpy"
        - ``import numpy as np`` -> alias = "np"
        - ``import numpy as npy`` -> alias = "npy" (any alias)
        - ``from numpy import *`` -> raises TranspileError

        Raises:
            TranspileError: If ``from numpy import *`` is used.
        """
        for node in ast.iter_child_nodes(self._tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "numpy":
                        self._alias = alias.asname or "numpy"
                    else:
                        self._existing_imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module == "numpy":
                    # Detect `from numpy import *`
                    for alias in node.names:
                        if alias.name == "*":
                            raise TranspileError(
                                "`from numpy import *` is not supported. "
                                "Use `import numpy as np` and call functions "
                                "as `np.sqrt()`, `np.random.random()`, etc.",
                                getattr(node, "lineno", 0),
                            )
                    # `from numpy import sqrt, pi` — treat as alias "numpy"
                    # so that bare names like sqrt() get handled by the
                    # transpiler's normal function dispatch
                    self._alias = "numpy"
                elif node.module:
                    self._existing_imports.add(node.module)

    # ── Pass 2: AST node rewrites ────────────────────────────────────

    def _is_np(self, node: ast.expr) -> bool:
        """Check if *node* is a Name node matching the numpy alias."""
        return isinstance(node, ast.Name) and node.id == self._alias

    def visit_Call(self, node: ast.Call) -> ast.AST:
        """Rewrite numpy function calls to stdlib equivalents.

        Handles three patterns:
        - ``np.random.<func>(...)`` -> ``random.<func>(...)``
        - ``np.<func>(...)`` -> ``math.<func>(...)`` or builtin
        - ``np.<unsupported>(...)`` -> raise TranspileError
        """
        self.generic_visit(node)  # recurse into child nodes first

        func = node.func

        # np.random.random() / np.random.normal() / np.random.uniform()
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "random"
            and self._is_np(func.value.value)
            and func.attr in self.RANDOM_REWRITES
        ):
            node.func = ast.Attribute(
                value=ast.Name(id="random", ctx=ast.Load()),
                attr=self.RANDOM_REWRITES[func.attr],
                ctx=ast.Load(),
            )
            return node

        # np.linalg.*, np.fft.* — entire submodules unsupported
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Attribute)
            and self._is_np(func.value.value)
            and func.value.attr in self._UNSUPPORTED_SUBMODULES
        ):
            raise TranspileError(
                f"`np.{func.value.attr}.{func.attr}()` is not supported. "
                f"The `numpy.{func.value.attr}` submodule has no EmojiASM equivalent.",
                getattr(node, "lineno", 0),
            )

        # np.sqrt(x), np.sin(x), np.abs(x), etc.
        if (
            isinstance(func, ast.Attribute)
            and self._is_np(func.value)
            and func.attr in self.FUNC_REWRITES
        ):
            module, fname = self.FUNC_REWRITES[func.attr]
            if module is None:
                # Builtin like abs()
                node.func = ast.Name(id=fname, ctx=ast.Load())
            else:
                node.func = ast.Attribute(
                    value=ast.Name(id=module, ctx=ast.Load()),
                    attr=fname,
                    ctx=ast.Load(),
                )
            return node

        # np.<unsupported_func>() — helpful error
        if (
            isinstance(func, ast.Attribute)
            and self._is_np(func.value)
            and func.attr in self._UNSUPPORTED_FUNCS
        ):
            raise TranspileError(
                f"`np.{func.attr}()` is not supported. "
                f"{self._UNSUPPORTED_FUNCS[func.attr]}.",
                getattr(node, "lineno", 0),
            )

        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        """Rewrite numpy constant references to math equivalents.

        Handles ``np.pi`` -> ``math.pi``, ``np.e`` -> ``math.e``.
        """
        self.generic_visit(node)

        if self._is_np(node.value) and node.attr in self.CONST_REWRITES:
            return ast.Attribute(
                value=ast.Name(id="math", ctx=ast.Load()),
                attr=self.CONST_REWRITES[node.attr],
                ctx=node.ctx,
            )
        return node

    # ── Pass 3: import replacement ────────────────────────────────────

    def _replace_imports(self) -> None:
        """Replace numpy import statements with ``import random`` and ``import math``.

        Filters out the numpy import and injects stdlib imports that are not
        already present in the source.
        """
        new_body: list[ast.stmt] = []
        for node in self._tree.body:
            if isinstance(node, ast.Import):
                # Filter out numpy from multi-import statements
                remaining = [a for a in node.names if a.name != "numpy"]
                if remaining:
                    node.names = remaining
                    new_body.append(node)
                # Add stdlib imports if not already present
                if "random" not in self._existing_imports:
                    new_body.append(
                        ast.Import(names=[ast.alias(name="random")])
                    )
                    self._existing_imports.add("random")
                if "math" not in self._existing_imports:
                    new_body.append(
                        ast.Import(names=[ast.alias(name="math")])
                    )
                    self._existing_imports.add("math")
            elif isinstance(node, ast.ImportFrom) and node.module == "numpy":
                # Drop `from numpy import ...` — functions are rewritten
                if "random" not in self._existing_imports:
                    new_body.append(
                        ast.Import(names=[ast.alias(name="random")])
                    )
                    self._existing_imports.add("random")
                if "math" not in self._existing_imports:
                    new_body.append(
                        ast.Import(names=[ast.alias(name="math")])
                    )
                    self._existing_imports.add("math")
            else:
                new_body.append(node)
        self._tree.body = new_body


def _rewrite_numpy(tree: ast.Module) -> ast.Module:
    """Rewrite numpy calls in the AST to stdlib equivalents.

    Thin wrapper around :class:`NumpyShim` for backward compatibility.
    """
    return NumpyShim(tree).apply()


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
        self._source_lines: list[str] = []

    def _emit(self, op: Op, arg=None, node=None):
        lineno = getattr(node, "lineno", 0) if node else 0
        src = ""
        if self._source_lines and 0 < lineno <= len(self._source_lines):
            src = self._source_lines[lineno - 1].strip()
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

        # Detect bare list literals (not [x] * N pattern)
        if isinstance(node.value, ast.List):
            raise TranspileError(
                "List literals are not supported. "
                "Use `arr = [0.0] * N` for fixed-size arrays.",
                node.lineno,
            )

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
                "Only `for x in range(N)` is supported. "
                "Iterating over lists, strings, or other iterables is not available.",
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
        allowed = {"random", "math", "numpy"}
        for alias in node.names:
            if alias.name not in allowed:
                raise TranspileError(
                    f"Unsupported import: '{alias.name}'. "
                    f"Use `import random` + `import math` instead. "
                    f"Supported: random.random(), random.uniform(), random.gauss(), "
                    f"math.sqrt(), math.sin(), math.cos(), math.exp(), math.log(), "
                    f"math.pi, abs(), min(), max().",
                    node.lineno,
                )
            self._imports.add(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        allowed = {"random", "math", "numpy"}
        if node.module not in allowed:
            raise TranspileError(
                f"Unsupported import: '{node.module}'. "
                f"Use `import random` + `import math` instead. "
                f"Supported: random.random(), random.uniform(), random.gauss(), "
                f"math.sqrt(), math.sin(), math.cos(), math.exp(), math.log(), "
                f"math.pi, abs(), min(), max().",
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

        # Build a readable function name for the error message
        func_name_readable = self._readable_func_name(node.func)
        suggestion = _SUGGESTION_MAP.get(func_name_readable, "")
        if not suggestion:
            # Try just the base function name (e.g. "math.floor" -> look up "math.floor")
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                dotted = f"{node.func.value.id}.{node.func.attr}"
                suggestion = _SUGGESTION_MAP.get(dotted, "")
            # Try just the function name for builtins
            if not suggestion and isinstance(node.func, ast.Name):
                suggestion = _SUGGESTION_MAP.get(node.func.id, "")

        msg = f"Unsupported function call: {func_name_readable}"
        if suggestion:
            msg += f". {suggestion}"
        else:
            msg += (
                ". Supported functions: print(), abs(), min(), max(), len(), sum(), "
                "random.random(), random.uniform(), random.gauss(), "
                "math.sqrt(), math.sin(), math.cos(), math.exp(), math.log()"
            )
        raise TranspileError(msg, node.lineno)

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

    @staticmethod
    def _readable_func_name(func_node: ast.expr) -> str:
        """Build a human-readable name from a function call node."""
        if isinstance(func_node, ast.Name):
            return func_node.id
        if isinstance(func_node, ast.Attribute):
            parts = []
            node = func_node
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            return ".".join(reversed(parts))
        return ast.dump(func_node)

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


# ── Auto-parallelization detection ───────────────────────────────────────


def _is_single_instance(tree: ast.Module) -> bool:
    """Check if a Python AST looks like a single Monte Carlo trial.

    Returns True if the program:
    (a) imports random or numpy,
    (b) has no for-loops with large range (>100), and
    (c) has a top-level assignment to ``result`` or the last statement is
        an expression.

    This is a simple heuristic — false positives are harmless (the program
    just gets run N times as-is).
    """
    has_random_import = False
    has_large_loop = False
    has_result_var = False
    last_is_expr = False

    for node in ast.walk(tree):
        # (a) Check for random/numpy import
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("random", "numpy"):
                    has_random_import = True
        elif isinstance(node, ast.ImportFrom):
            if node.module in ("random", "numpy"):
                has_random_import = True

        # (b) Check for large for-loops
        if isinstance(node, ast.For):
            if (
                isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name)
                and node.iter.func.id == "range"
            ):
                args = node.iter.args
                # Check if range arg is a constant > 100
                if len(args) >= 1:
                    arg = args[-1] if len(args) <= 2 else args[1]
                    if isinstance(arg, ast.Constant) and isinstance(
                        arg.value, (int, float)
                    ):
                        if arg.value > 100:
                            has_large_loop = True

    # (c) Check for result variable assignment or expression as last stmt
    if tree.body:
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == "result":
                        has_result_var = True
            elif isinstance(stmt, ast.AugAssign):
                if (
                    isinstance(stmt.target, ast.Name)
                    and stmt.target.id == "result"
                ):
                    has_result_var = True

        last_stmt = tree.body[-1]
        if isinstance(last_stmt, ast.Expr):
            last_is_expr = True

    return has_random_import and not has_large_loop and (
        has_result_var or last_is_expr
    )


def _ensure_result_capture(tree: ast.Module) -> ast.Module:
    """Ensure the program's result value is printed for CPU capture.

    If the last statement is ``result = expr``, appends ``print(result)``
    so the value is available in stdout (CPU path) and also remains on
    the stack after the PRINTLN opcode is followed by a LOAD+HALT
    sequence.

    If there is a variable named ``result`` anywhere, appends
    ``print(result)`` at the end so the value ends up in stdout.

    Returns the (possibly modified) AST with locations fixed.
    """
    if not tree.body:
        return tree

    has_result_var = False
    already_prints_result = False

    for stmt in tree.body:
        # Check for assignment to 'result'
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "result":
                    has_result_var = True
        elif isinstance(stmt, ast.AugAssign):
            if (
                isinstance(stmt.target, ast.Name)
                and stmt.target.id == "result"
            ):
                has_result_var = True

        # Check if there's already a print(result) call
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if (
                isinstance(call.func, ast.Name)
                and call.func.id == "print"
                and len(call.args) == 1
                and isinstance(call.args[0], ast.Name)
                and call.args[0].id == "result"
            ):
                already_prints_result = True

    if has_result_var and not already_prints_result:
        # Append: print(result)
        print_call = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="print", ctx=ast.Load()),
                args=[ast.Name(id="result", ctx=ast.Load())],
                keywords=[],
            )
        )
        tree.body.append(print_call)
        ast.fix_missing_locations(tree)

    return tree


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

    tree = _rewrite_numpy(tree)

    compiler = PythonTranspiler()
    compiler._source_lines = source.splitlines()
    compiler.visit_Module(tree)
    return compiler.program


def transpile_to_source(source: str) -> str:
    """Transpile Python source to EmojiASM source text.

    Convenience function that transpiles and then disassembles.
    """
    program = transpile(source)
    return disassemble(program)
