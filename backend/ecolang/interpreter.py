"""EcoLang interpreter module.

This module implements a small, safe interpreter for the EcoLang toy language
used in the project. It focuses on clarity and safety for running untrusted
user programs by:

- using AST-based expression evaluation with explicit node whitelisting
- enforcing runtime limits (steps, loops, time, output size)
- providing a small set of statements (say/let/ask/warn/if/repeat/etc.)

The interpreter is intentionally simple and instrumented with operation-cost
accounting so the server can estimate energy usage. Comments and docstrings in
this file explain the expected inputs, outputs and error behaviours.
"""

import ast
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from . import subprocess_runner


class EvalError(Exception):
    """Raised when expression evaluation fails or a disallowed AST element is seen.

    This exception is used to signal parse/validation errors in expressions and
    is intentionally narrow: expression evaluation code should translate this
    into the interpreter's RUNTIME_ERROR responses rather than leaking Python
    exceptions to callers.

    Attributes:
        column: optional 1-based column where the error occurred within the expression
        text: optional original expression text (single line)
    """

    def __init__(self, message: str, *, column: Optional[int] = None, text: Optional[str] = None):
        super().__init__(message)
        self.column = column
        self.text = text



class SafeEvaluator(ast.NodeVisitor):
    """Minimal AST evaluator for simple expressions used by EcoLang.

    The evaluator only supports numeric and boolean operations and variable
    lookup from a provided `env` dict. Function calls, attribute access and
    other potentially dangerous constructs are rejected at parse-time in
    `eval_expr` (see module-level AST walk). This class focuses on the
    trusted subset of AST nodes the language exposes.will evaluate more

    Args:
        env: mapping of variable names to values made available to expressions.
    """

    def __init__(self, env: Dict[str, Any]):
        self.env = env

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            # Support string concatenation by coercing to string when either side is a string
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Pow):
            # Guard against huge exponents
            if abs(right) > 8:
                raise EvalError("Exponent too large; max 8")
            return left ** right
        raise EvalError(f"Unsupported binary op {node.op}")

    def visit_Compare(self, node):
        # support simple comparisons: left <op> right (single comparator)
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise EvalError("Chained comparisons not supported")
        left = self.visit(node.left)
        right = self.visit(node.comparators[0])
        op = node.ops[0]
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.Lt):
            return left < right
        if isinstance(op, ast.LtE):
            return left <= right
        if isinstance(op, ast.Gt):
            return left > right
        if isinstance(op, ast.GtE):
            return left >= right
        raise EvalError(f"Unsupported comparison {type(op).__name__}")

    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.Not):
            return not operand
        raise EvalError("Unsupported unary op")

    def visit_BoolOp(self, node):
        # Implement short-circuit and/or
        if isinstance(node.op, ast.And):
            for v in node.values:
                if not self.visit(v):
                    return False
            return True
        if isinstance(node.op, ast.Or):
            for v in node.values:
                if self.visit(v):
                    return True
            return False
        raise EvalError("Unsupported boolean op")

    def visit_Num(self, node):
        return node.n

    def visit_Constant(self, node):
        return node.value

    def visit_Name(self, node):
        if node.id in self.env:
            return self.env[node.id]
        if node.id == "true":
            return True
        if node.id == "false":
            return False
        raise EvalError(f"Undefined variable '{node.id}'")

    def visit_Call(self, node):
        # Allow a limited set of safe builtin calls: len/length, toNumber, toString,
        # array(), append(a,x), at(a,i), ecoOps()
        if not isinstance(node.func, ast.Name):
            raise EvalError("Unsupported call target")
        name = node.func.id
        # Evaluate arguments first
        args = [self.visit(a) for a in node.args]
        if name in ("len", "length"):
            if len(args) != 1:
                raise EvalError("length expects 1 arg")
            return len(args[0])
        if name == "toNumber":
            if len(args) != 1:
                raise EvalError("toNumber expects 1 arg")
            try:
                return float(args[0]) if (isinstance(args[0], str) and ("." in args[0])) else int(args[0])
            except Exception:
                raise EvalError("toNumber failed")
        if name == "toString":
            if len(args) != 1:
                raise EvalError("toString expects 1 arg")
            return str(args[0])
        if name == "array":
            if args:
                raise EvalError("array expects 0 args")
            return []
        if name == "append":
            if len(args) != 2:
                raise EvalError("append expects 2 args")
            # functional append: returns a new array
            if not isinstance(args[0], list):
                raise EvalError("append first arg must be array")
            arr = list(args[0])
            arr.append(args[1])
            return arr
        if name == "at":
            if len(args) != 2:
                raise EvalError("at expects 2 args")
            a, idx = args
            if not isinstance(a, list):
                raise EvalError("at first arg must be array")
            try:
                return a[int(idx)]
            except Exception:
                raise EvalError("index out of range")
        if name == "ecoOps":
            # returns current ops from env injection
            return int(self.env.get("_eco_ops", 0))
        raise EvalError("Unsupported function call")

    def generic_visit(self, node):
        raise EvalError(f"Unsupported expression: {type(node).__name__}")


def eval_expr(expr: str, env: Dict[str, Any]):
    """Parse and safely evaluate a single expression string.

    This function performs two responsibilities:
    1. Parse the expression into an AST and validate that no disallowed nodes
       (calls, attribute access, imports, comprehensions, function/class defs,
       subscripts, etc.) are present. Rejecting these at the AST level keeps
       evaluation simple and safe.
    2. Use the `SafeEvaluator` to compute the value of the expression using a
       restricted environment `env`.

    Args:
        expr: expression source text (e.g. "a + 3").
        env: mapping of allowed names to values used during evaluation.

    Returns:
        The Python value resulting from evaluating the expression.

    Raises:
        EvalError: if parsing fails or disallowed AST nodes are present.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        # Hide Python SyntaxError; elevate to EvalError carrying a basic column
        # and the original expression text for better diagnostics at call sites.
        col = None
        try:
            col = int(getattr(e, "offset", None) or 1)
        except Exception:
            col = 1
        raise EvalError("Syntax error in expression", column=col, text=expr) from e

    # Walk the AST and explicitly disallow dangerous constructs. Doing this
    # centrally (instead of relying on SafeEvaluator.generic_visit) gives a
    # clear security boundary and makes approval decisions explicit.
    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.Attribute,
                ast.Import,
                ast.ImportFrom,
                ast.Lambda,
                ast.DictComp,
                ast.ListComp,
                ast.SetComp,
                ast.GeneratorExp,
                ast.Yield,
                ast.YieldFrom,
                ast.FunctionDef,
                ast.ClassDef,
                ast.Subscript,
                ast.Global,
                ast.Nonlocal,
            ),
        ):
            raise EvalError(f"Unsupported expression element: {type(node).__name__}")
        # Allow only a safe set of function calls
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in (
                "len",
                "length",
                "toNumber",
                "toString",
                "array",
                "append",
                "at",
                "ecoOps",
            ):
                raise EvalError("Unsupported function call")
        # explicitly disallow a few dangerous builtin names
        if isinstance(node, ast.Name) and node.id in ("__import__", "eval", "exec", "open", "os", "sys"):
            raise EvalError(f"Unsupported name in expression: {node.id}")

    evaluator = SafeEvaluator(env)
    try:
        return evaluator.visit(tree)
    except EvalError:
        raise
    except Exception as e:
        # Convert any unexpected Python errors (TypeError, ZeroDivisionError, etc.)
        # into a friendly EvalError so the interpreter can report them cleanly.
        raise EvalError(str(e))


class Interpreter:
    """Top-level EcoLang interpreter class.

    Responsibilities:
    - execute EcoLang source code (list of statement lines),
    - enforce runtime limits (steps, loops, wall-clock, output size),
    - account for operation counts so the server can estimate energy use.

    Tunable attributes (defaults are set in __init__):
    - ops_map: estimated operation cost map used to compute total_ops
    - energy_per_op_J, idle_power_W, co2_per_kwh_g: eco estimation parameters
    - max_steps, max_loop, max_time_s, max_output_chars: runtime safety caps
    """

    def __init__(self):
        # Estimated operation cost mapping used to accumulate `total_ops`.
        self.ops_map = {
            "print": 50,
            "loop_check": 5,
            "math": 10,
            "assign": 5,
            "io": 200,
            "optimize": 1000,
            "other": 5,
            "func_call": 20,
        }
        # Eco/energy estimation tunables (can be overridden via settings)
        self.energy_per_op_J = 1e-9
        self.idle_power_W = 0.5
        self.co2_per_kwh_g = 475
        # Safety limits enforced per-run
        self.max_steps = 100000
        self.max_loop = 10000
        self.max_time_s = 1.5
        self.max_output_chars = 5000
        # Function-related constraints (green-friendly defaults)
        self.max_func_params = 3
        self.max_call_depth = 5
        # Functions registry for this interpreter run: name -> {args: [...], block: [...]}
        self.functions = {}
        # Current call depth counter
        self._call_depth = 0
        # Constants defined via 'const'
        self._consts = set()

    # --- Error helpers -------------------------------------------------
    def _err(self, code: str, message: str, *, line: int, column: int = 1, line_text: Optional[str] = None, hint: Optional[str] = None) -> Dict[str, Any]:
        err: Dict[str, Any] = {"code": code, "message": message, "line": line, "column": column}
        if line_text is not None:
            err["context"] = {"line_text": line_text}
        if hint:
            err["hint"] = hint
        return err

    def _with_position(self, err: Optional[Dict[str, Any]], *, line: int, column: int = 1, line_text: Optional[str] = None, hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not err:
            return None
        # Avoid overwriting if already present
        if "line" not in err:
            err["line"] = line
        if "column" not in err:
            err["column"] = column
        if line_text is not None and "context" not in err:
            err["context"] = {"line_text": line_text}
        if hint and "hint" not in err:
            err["hint"] = hint
        return err

    def _run_sub_interpreter(
        self,
        code: str,
        inputs: Dict[str, Any],
        settings: Dict[str, Any],
        env: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run a fresh Interpreter for nested blocks to preserve state.

        The original implementation used Interpreter().run directly; this
        helper keeps the behaviour but centralizes the call site.
        """
        # Run a fresh Interpreter but seed its environment so nested blocks
        # can access variables from the outer scope. This isolates state between
        # nested blocks while allowing variable reads from `env` to flow in.
        it = Interpreter()
        # inherit limits from parent unless overridden in settings
        it.max_steps = settings.get("max_steps", self.max_steps)
        it.max_loop = settings.get("max_loop", self.max_loop)
        it.max_time_s = settings.get("max_time_s", self.max_time_s)
        it.max_output_chars = settings.get("max_output_chars", self.max_output_chars)
        out_lines, warnings, total_ops, maybe_err, start_time = it._execute_core(
            code, inputs, settings, initial_env=env
        )
        if maybe_err.get("errors"):
            return {
                "output": "\n".join(out_lines),
                "warnings": warnings,
                "eco": None,
                "errors": maybe_err.get("errors"),
            }
        duration_s = max(0.000001, time.time() - start_time)
        eco = it._compute_eco(total_ops, duration_s)
        return {
            "output": "\n".join(out_lines) + ("\n" if out_lines else ""),
            "warnings": warnings,
            "eco": eco,
            "errors": None,
        }

    def _handle_if(  # noqa: C901
        self,
        lines: List[str],
        i: int,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        output_lines: List[str],
        warnings: List[str],
        total_ops: int,
        ops_scale: float,
    ) -> Tuple[
        int,
        int,
        List[str],
        List[str],
        Optional[Dict[str, Any]],
    ]:
        """Evaluate an if/then/else block starting at index i.

        The method extracts the block between the starting `if` and the matching
        `end`, finds an optional top-level `else`, evaluates the condition using
        `eval_expr`, and executes the chosen branch by invoking a nested
        interpreter via `_run_sub_interpreter`.

        Returns a tuple (new_i, ops_delta, out_add, warn_add, error_or_none) in
        the same normalized shape used by the statement dispatching code.
        """
        line = lines[i].strip()
        # Validate header shape: must end with ' then'
        if not line.endswith(" then"):
            return (
                i,
                0,
                [],
                [],
                self._err(
                    "SYNTAX_ERROR",
                    "Expected 'then' after if condition",
                    line=i + 1,
                    column=len(line) + 1,
                    line_text=lines[i],
                    hint="Write: if <condition> then",
                ),
            )
        cond_expr = line[3:-5].strip()
        try:
            block, end_idx = self._extract_block_for_run(lines, i + 1)
        except EvalError as e:
            return (
                i,
                0,
                [],
                [],
                self._err("SYNTAX_ERROR", str(e), line=i + 1, column=1, line_text=lines[i], hint="Add a matching 'end' for this 'if'."),
            )

        # find optional else/elif at top level. We only support a single elif.
        else_idx: Optional[int] = None
        elif_idx: Optional[int] = None
        elif_cond: Optional[str] = None
        depth = 0
        for j, r in enumerate(block):
            t = r.strip()
            if t.startswith("if ") or t.startswith("repeat ") or t.startswith("while ") or t.startswith("for "):
                depth += 1
                continue
            if t == "end":
                if depth > 0:
                    depth -= 1
                continue
            if depth == 0:
                if t == "else" and else_idx is None:
                    else_idx = j
                    break
                if t.startswith("elif ") and t.endswith(" then") and elif_idx is None:
                    elif_idx = j
                    elif_cond = t[len("elif "):-len(" then")].strip()
        try:
            cond_val = eval_expr(cond_expr, env)
        except EvalError as e:
            base_col = 1 + len("if ")
            col = base_col + (e.column or 1) - 1
            return (
                i,
                0,
                [],
                [],
                self._err("RUNTIME_ERROR", str(e), line=i + 1, column=col, line_text=lines[i].strip(), hint="Fix the condition expression after 'if'."),
            )

        # Determine segment ranges
        end_then = len(block)
        if elif_idx is not None:
            end_then = min(end_then, elif_idx)
        if else_idx is not None:
            end_then = min(end_then, else_idx)

        if bool(cond_val):
            exec_block = block[:end_then]
        else:
            if elif_idx is not None and elif_cond is not None:
                # evaluate elif condition
                try:
                    cond2 = eval_expr(elif_cond, env)
                except EvalError as e:
                    base_col = 1 + len("if ")
                    col = base_col + (e.column or 1) - 1
                    return (
                        i,
                        0,
                        [],
                        [],
                        self._err("RUNTIME_ERROR", str(e), line=i + 1, column=col, line_text=lines[i].strip(), hint="Fix the elif condition."),
                    )
                if bool(cond2):
                    end_elif_block = else_idx if else_idx is not None else len(block)
                    exec_block = block[elif_idx + 1 : end_elif_block]
                else:
                    exec_block = block[else_idx + 1 :] if else_idx is not None else []
            else:
                exec_block = block[else_idx + 1 :] if else_idx is not None else []

        # Run the selected branch in a fresh interpreter to avoid mutating the
        # outer scope. Nested runs inherit eco/limit settings.
        sub_code = "\n".join(exec_block)
        sub_res = self._run_sub_interpreter(
            sub_code,
            inputs=inputs,
            settings={
                "energy_per_op_J": self.energy_per_op_J,
                "idle_power_W": self.idle_power_W,
                "co2_per_kwh_g": self.co2_per_kwh_g,
            },
            env=env,
        )
        if sub_res.get("errors"):
            return (i, 0, [], [], sub_res)
        out_add: List[str] = []
        if sub_res.get("output"):
            out_add = sub_res["output"].splitlines()
        warn_add = sub_res.get("warnings", []) or []
        ops_delta = sub_res.get("eco", {}).get("total_ops", 0)
        return (end_idx + 1, ops_delta, out_add, warn_add, None)

    def _handle_repeat(
        self,
        lines: List[str],
        i: int,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        output_lines: List[str],
        warnings: List[str],
        total_ops: int,
        ops_scale: float,
    ) -> Tuple[
        int,
        int,
        List[str],
        List[str],
        Optional[Dict[str, Any]],
    ]:
        """Evaluate a `repeat N times` block.

        Behaviour notes:
        - If `n` exceeds `self.max_loop` it's truncated and a warning is added.
        - Each iteration is executed using a fresh sub-interpreter to limit
          cross-iteration state sharing.

        Returns:
            (new_index, ops_delta, output_lines_added, warnings_added, error_or_none)
        """
        line = lines[i].strip()
        if not line.endswith(" times"):
            return (
                i,
                0,
                [],
                [],
                self._err(
                    "SYNTAX_ERROR",
                    "Expected 'times' at end of repeat",
                    line=i + 1,
                    column=len(line) + 1,
                    line_text=lines[i],
                    hint="Write: repeat <number> times",
                ),
            )
        mid = line[len("repeat ") : -len(" times")].strip()
        try:
            n = int(mid)
        except Exception:
            return (
                i,
                0,
                [],
                [],
                self._err("SYNTAX_ERROR", "Invalid repeat count", line=i + 1, column=len("repeat ") + 1, line_text=lines[i], hint="Use: repeat <number> times"),
            )

        try:
            block, end_idx = self._extract_block_for_run(lines, i + 1)
        except EvalError as e:
            return (i, 0, [], [], self._err("SYNTAX_ERROR", str(e), line=i + 1, column=1, line_text=lines[i], hint="Add a matching 'end' for this 'repeat'."))

        # enforce configured max loop count and produce a warning if trimmed
        if n > self.max_loop:
            warn_msg = f"Repeat count limited to {self.max_loop}"
            n = self.max_loop

        sub_code = "\n".join(block)
        out_add: List[str] = []
        warn_add: List[str] = []
        ops_delta = 0

        for _ in range(n):
            # check step budget before each iteration to avoid runaway work
            if total_ops + ops_delta > self.max_steps:
                warn_add.append("Step limit exceeded inside repeat; aborted")
                break
            # account for a small loop-check cost per iteration
            ops_delta += int(self.ops_map.get("loop_check", 5) * ops_scale)
            sub_res = self._run_sub_interpreter(
                sub_code,
                inputs=inputs,
                settings={
                    "energy_per_op_J": self.energy_per_op_J,
                    "idle_power_W": self.idle_power_W,
                    "co2_per_kwh_g": self.co2_per_kwh_g,
                },
                env=env,
            )
            if sub_res.get("errors"):
                return (i, 0, [], [], sub_res)
            if sub_res.get("output"):
                out_add.extend(sub_res["output"].splitlines())
            warn_add.extend(sub_res.get("warnings", []))
            ops_delta += sub_res.get("eco", {}).get("total_ops", 0)

        # if we limited the repeat count, include the warning
        if 'warn_msg' in locals():
            warn_add.insert(0, warn_msg)
        return (end_idx + 1, ops_delta, out_add, warn_add, None)

    def _find_else_index(self, block: List[str]) -> Optional[int]:
        """Return the index of a top-level `else` in `block`, or None.

        Nested `if`/`repeat` blocks are tracked by `depth` so we only report an
        `else` that belongs to the top-level block.
        """
        depth = 0
        for j, r in enumerate(block):
            t = r.strip()
            if t.startswith("if ") or t.startswith("repeat ") or t.startswith("while ") or t.startswith("for "):
                depth += 1
                continue
            if t == "end":
                if depth > 0:
                    depth -= 1
                continue
            if t == "else" and depth == 0:
                return j
        return None  # type: ignore (to review logic)

    def _handle_say(
        self, line: str, env: Dict[str, Any], ops_scale: float
    ) -> Tuple[Optional[int], List[str], List[str], int, Optional[Dict[str, Any]]]:
        """Handle a `say <expr>` statement.

        Returns (step_inc, out_add, warn_add, ops_delta, error_or_none).
        """
        # extract expression to print after the 'say ' prefix
        expr = line[4:].strip()
        try:
            val = eval_expr(expr, env)
        except EvalError as e:
            # Column relative to start of expression after 'say '
            col = len("say ") + (e.column or 1)
            return (None, [], [], 0, {"code": "RUNTIME_ERROR", "message": str(e), "column": col})
        # output is stringified; _execute_core will check output length caps
        output = str(val)
        ops_delta = int(self.ops_map.get("print", 50) * ops_scale)
        return (1, [output], [], ops_delta, None)

    def _handle_let(
        self, line: str, env: Dict[str, Any], ops_scale: float
    ) -> Tuple[Optional[int], List[str], List[str], int, Optional[Dict[str, Any]]]:
        """Handle a `let <name> = <expr>` assignment that stores value in `env`.

        Returns (step_inc, out_add, warn_add, ops_delta, error_or_none).
        """
        # parse `let name = expr` and bind into `env`
        rest = line[4:].strip()
        if "=" not in rest:
            return (
                None,
                [],
                [],
                0,
                {"code": "SYNTAX_ERROR", "message": "Expected '=' in let statement", "hint": "Use: let name = expr"},
            )
        name, expr = rest.split("=", 1)
        name = name.strip()
        expr = expr.strip()
        if not name.isidentifier():
            return (
                None,
                [],
                [],
                0,
                {"code": "SYNTAX_ERROR", "message": "Invalid identifier in let", "hint": "Identifiers must be letters/digits/_ and not start with a digit."},
            )
        if name in getattr(self, "_consts", set()) and name in env:
            return (
                None,
                [],
                [],
                0,
                {"code": "RUNTIME_ERROR", "message": f"Cannot reassign const '{name}'"},
            )
        try:
            val = eval_expr(expr, env)
        except EvalError as e:
            col = len("let ") + rest.find("=") + 1 + (e.column or 1)
            return (None, [], [], 0, {"code": "RUNTIME_ERROR", "message": str(e), "column": col})
        # assignment writes into the current environment
        env[name] = val
        ops_delta = int(self.ops_map.get("assign", 5) * ops_scale)
        return (1, [], [], ops_delta, None)

    def _dispatch_const(self, line: str, i: int, env: Dict[str, Any], ops_scale: float):
        rest = line[len("const "):].strip()
        if "=" not in rest:
            return i, 0, [], [], {"code": "SYNTAX_ERROR", "message": "Expected '=' in const", "hint": "Use: const NAME = expr"}
        name, expr = rest.split("=", 1)
        name = name.strip()
        expr = expr.strip()
        if not name.isidentifier():
            return i, 0, [], [], {"code": "SYNTAX_ERROR", "message": "Invalid const name"}
        if name in env:
            return i, 0, [], [], {"code": "RUNTIME_ERROR", "message": f"'{name}' already defined"}
        try:
            val = eval_expr(expr, env)
        except EvalError as e:
            return i, 0, [], [], {"code": "RUNTIME_ERROR", "message": str(e)}
        env[name] = val
        getattr(self, "_consts").add(name)
        return i + 1, int(self.ops_map.get("assign", 5) * ops_scale), [], [], None

    def _handle_ask(
        self,
        line: str,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        ops_scale: float,
    ) -> Tuple[
        Optional[int],
        List[str],
        List[str],
        int,
        Optional[Dict[str, Any]],
    ]:
        """Handle `ask <name>` which consumes a provided input value.

        If the requested input is missing from `inputs`, return a RUNTIME_ERROR.
        """
        name = line[4:].strip()
        if not name.isidentifier():
            return (
                None,
                [],
                [],
                0,
                {"code": "SYNTAX_ERROR", "message": "Invalid identifier in ask", "hint": "Use: ask name"},
            )
        if name in inputs:
            env[name] = inputs[name]
        else:
            return (
                None,
                [],
                [],
                0,
                {"code": "RUNTIME_ERROR", "message": f"Missing input for '{name}'"},
            )
        ops_delta = int(self.ops_map.get("io", 200) * ops_scale)
        return (1, [], [], ops_delta, None)

    def _handle_warn(
        self, line: str, env: Dict[str, Any], ops_scale: float
    ) -> Tuple[Optional[int], List[str], List[str], int, Optional[Dict[str, Any]]]:
        """Handle `warn <expr>` which evaluates an expression and records a warning."""
        expr = line[5:].strip()
        try:
            val = eval_expr(expr, env)
        except EvalError as e:
            return (None, [], [], 0, {"code": "RUNTIME_ERROR", "message": str(e)})
        warn = str(val)
        ops_delta = int(self.ops_map.get("other", 5) * ops_scale)
        return (1, [], [warn], ops_delta, None)

    def _handle_ecotip(
        self, total_ops: int, ops_scale: float
    ) -> Tuple[int, List[str], List[str], int, Optional[Dict[str, Any]]]:
        """Return a small ecoTip message based on `total_ops`.

        This is a helper used by the `ecoTip` statement; it returns the tuple
        shaped like other handlers: (step_inc, out_add, warn_add, ops_delta, err).
        """
        tips = [
            "Turn off unused devices",
            "Reduce loop counts",
            "Prefer simpler math operations",
        ]
        tip = tips[total_ops % len(tips)]
        ops_delta = int(self.ops_map.get("other", 5) * ops_scale)
        return (1, [f"ecoTip: {tip}"], [], ops_delta, None)

    def _extract_block_for_run(
        self,
        lines: List[str],
        start_idx: int,
    ) -> Tuple[List[str], int]:
        """Extract lines until matching 'end', handling nested blocks.
        Returns (block_lines, index_of_end_line). This mirrors the local
        `extract_block` used inside `run` so helper methods can reuse it.
        """
        block: List[str] = []
        depth = 0
        j = start_idx
        while j < len(lines):
            raw = lines[j]
            txt = raw.strip()
            # track nested starts
            if txt.startswith("if ") or txt.startswith("repeat ") or txt.startswith("func ") or txt.startswith("while ") or txt.startswith("for "):
                depth += 1
                block.append(raw)
            elif txt == "end":
                if depth == 0:
                    return block, j
                depth -= 1
                block.append(raw)
            else:
                block.append(raw)
            j += 1
        # if we reach here, unmatched block
        raise EvalError("Missing end for block")

    # --- Inline block execution helper (preserves env mutations) -----------
    def _execute_block_inline(
        self,
        block: List[str],
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        ops_scale: float,
    ) -> Tuple[List[str], List[str], int, Optional[Dict[str, Any]]]:
        """Execute a block of lines reusing the given env.

        Returns (out_add, warn_add, ops_delta, err_or_none).
        """
        out_lines: List[str] = []
        warn_add: List[str] = []
        ops_delta = 0
        i = 0
        start_wall = time.time()
        steps_local = 0
        while i < len(block):
            raw = block[i]
            if time.time() - start_wall > self.max_time_s:
                return out_lines, warn_add, ops_delta, {"code": "TIMEOUT", "message": "Time limit exceeded in block"}
            if steps_local > self.max_steps:
                warn_add.append("Step limit exceeded in block")
                return out_lines, warn_add, ops_delta, {"code": "STEP_LIMIT", "message": "Step limit exceeded in block"}
            line = raw.strip()
            if not line or line.startswith("#"):
                i += 1
                continue
            steps_local += 1
            ops_delta += self.ops_map.get("other", 5)
            new_i, inner_ops, out_add, w_add, err = self._dispatch_statement(
                block,
                i,
                line,
                env,
                inputs,
                out_lines,
                warn_add,
                ops_delta,
                ops_scale,
            )
            if err:
                return out_lines, warn_add, ops_delta, err
            if out_add:
                for o in out_add:
                    if sum(len(x) for x in out_lines) + len(o) > self.max_output_chars:
                        return out_lines, warn_add, ops_delta, {"code": "OUTPUT_LIMIT", "message": "Output length limit reached in block"}
                    out_lines.append(o)
            if w_add:
                warn_add.extend(w_add)
            ops_delta += inner_ops
            i = new_i
        return out_lines, warn_add, ops_delta, None

    def _dispatch_statement(
        self,
        lines: List[str],
        i: int,
        line: str,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        output_lines: List[str],
        warnings: List[str],
        total_ops: int,
        ops_scale: float,
    ) -> Tuple[
        int,
        int,
        List[str],
        List[str],
        Optional[Dict[str, Any]],
    ]:
        """Dispatch a single statement at index `i`.

        Returns (new_i, ops_delta, out_add, warn_add, error_or_none)
        """
        # minimal-dispatch: map first token to a handler that returns the
        # unified tuple. This reduces branching inside this function.
        token = line.split(None, 1)[0] if line else ""

        # handle single-word special tokens first
        if line == "ecoTip":
            return self._dispatch_ecotip(total_ops, i, ops_scale)
        if token == "savePower":
            return self._dispatch_save_power(line, i, env)
        if token == "else":
            return (
                i,
                0,
                [],
                [],
                self._err(
                    "SYNTAX_ERROR",
                    "'else' without matching 'if'",
                    line=i + 1,
                    column=1,
                    line_text=line,
                    hint="Place 'else' inside an if..end block.",
                ),
            )
        if token == "end":
            return (
                i,
                0,
                [],
                [],
                self._err(
                    "SYNTAX_ERROR",
                    "Unexpected 'end'",
                    line=i + 1,
                    column=1,
                    line_text=line,
                    hint="Remove extra 'end' or match it with if/repeat/func.",
                ),
            )

        dispatch_map = {
            "say": lambda: self._dispatch_simple_prefix(
                line, i, env, ops_scale
            ),
            "let": lambda: self._dispatch_simple_prefix(
                line, i, env, ops_scale
            ),
            "const": lambda: self._dispatch_const(line, i, env, ops_scale),
            "warn": lambda: self._dispatch_simple_prefix(
                line, i, env, ops_scale
            ),
            "ask": lambda: self._dispatch_ask(
                line, i, env, inputs, ops_scale
            ),
            "func": lambda: self._dispatch_func_def(lines, i),
            "call": lambda: self._dispatch_func_call(line, i, env, inputs, ops_scale),
            "if": lambda: self._dispatch_control_if(
                lines, i, env, inputs, output_lines, warnings, total_ops, ops_scale
            ),
            "repeat": lambda: self._dispatch_control_repeat(
                lines, i, env, inputs, output_lines, warnings, total_ops, ops_scale
            ),
            "while": lambda: self._dispatch_control_while(
                lines, i, env, inputs, output_lines, warnings, total_ops, ops_scale
            ),
            "for": lambda: self._dispatch_control_for(
                lines, i, env, inputs, output_lines, warnings, total_ops, ops_scale
            ),
            # future: while/for/withBudget can be added here when implemented
        }

        handler = dispatch_map.get(token)
        if not handler:
            return (
                i,
                0,
                [],
                [],
                self._err("SYNTAX_ERROR", f"Unknown statement: {line}", line=i + 1, column=1, line_text=line, hint="Check the command name or syntax."),
            )
        res = handler()
        if not res:
            return (
                i,
                0,
                [],
                [],
                self._err("SYNTAX_ERROR", f"Unknown statement: {line}", line=i + 1, column=1, line_text=line, hint="Check the command name or syntax."),
            )
        # all handlers return normalized (new_i, ops_delta, out_add, warn_add, err)
        try:
            new_i, ops_delta, out_add, warn_add, err = res
        except Exception:
            return (
                i,
                0,
                [],
                [],
                {"code": "INTERNAL", "message": "Invalid handler result"},
            )
        if err:
            # Enrich with position info if missing
            return i, 0, [], [], self._with_position(err, line=i + 1, column=err.get("column", 1), line_text=line)
        return new_i, ops_delta, out_add, warn_add, None

    def _dispatch_func_def(self, lines: List[str], i: int):
        # Parse: func name [arg1 arg2 ...]\n ... \n end
        header = lines[i].strip()
        rest = header[len("func "):].strip()
        parts = rest.split()
        if not parts:
            return (
                i,
                0,
                [],
                [],
                self._err("SYNTAX_ERROR", "Missing function name", line=i + 1, column=1, line_text=lines[i], hint="Use: func name [args]"),
            )
        name = parts[0]
        if not name.isidentifier():
            return (
                i,
                0,
                [],
                [],
                self._err("SYNTAX_ERROR", "Invalid function name", line=i + 1, column=len("func ") + 1, line_text=lines[i]),
            )
        args = parts[1:]
        if len(args) > self.max_func_params:
            return (
                i,
                0,
                [],
                [],
                self._err("SYNTAX_ERROR", f"Too many params (max {self.max_func_params})", line=i + 1, column=1, line_text=lines[i]),
            )
        try:
            block, end_idx = self._extract_block_for_run(lines, i + 1)
        except EvalError as e:
            return (i, 0, [], [], self._err("SYNTAX_ERROR", str(e), line=i + 1, column=1, line_text=lines[i], hint="Add a matching 'end' for this 'func'."))
        # store function (exclude trailing 'end' inside block if present at top level)
        self.functions[name] = {"args": args, "block": block}
        # small op cost for definition bookkeeping
        return end_idx + 1, int(self.ops_map.get("other", 5)), [], [f"func defined: {name}"], None

    def _dispatch_func_call(
        self,
        line: str,
        i: int,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        ops_scale: float,
    ):
        # Syntax: call name [with expr1, expr2, ...] [into var]
        # Examples:
        #   call add with 1, 2 into result
        #   call greet with "Eco"  (prints return value if no 'into')
        txt = line[len("call "):].strip()
        if not txt:
            return i, 0, [], [], self._err("SYNTAX_ERROR", "Missing function name", line=i + 1, column=1, line_text=line)
        # split into main and optional 'into'
        into_var = None
        if " into " in txt:
            main, into_part = txt.split(" into ", 1)
            into_var = into_part.strip()
            if not into_var.isidentifier():
                return i, 0, [], [], self._err("SYNTAX_ERROR", "Invalid target after 'into'", line=i + 1, column=line.find(" into ") + len(" into ") + 1, line_text=line)
        else:
            main = txt
        # handle optional 'with'
        if " with " in main:
            name_str, args_str = main.split(" with ", 1)
            name = name_str.strip()
            args_exprs = [s.strip() for s in args_str.split(",") if s.strip()]
        else:
            name = main.strip()
            args_exprs = []
        if not name.isidentifier():
            return i, 0, [], [], self._err("SYNTAX_ERROR", "Invalid function name", line=i + 1, column=len("call ") + 1, line_text=line)
        if name not in self.functions:
            return i, 0, [], [], self._err("RUNTIME_ERROR", f"Unknown function '{name}'", line=i + 1, column=len("call ") + 1, line_text=line)
        spec = self.functions[name]
        if len(args_exprs) != len(spec["args"]):
            return i, 0, [], [], self._err("RUNTIME_ERROR", "Argument count mismatch", line=i + 1, column=line.find(" with ") + 1 if " with " in line else len("call ") + 1, line_text=line)
        # evaluate arguments in current env
        call_args: Dict[str, Any] = {}
        for arg_name, expr in zip(spec["args"], args_exprs):
            try:
                call_args[arg_name] = eval_expr(expr, env)
            except EvalError as e:
                # For argument expressions, best-effort column after 'with '
                base = line.find(" with ")
                base = (base + len(" with ")) if base >= 0 else len("call ")
                return i, 0, [], [], self._err("RUNTIME_ERROR", str(e), line=i + 1, column=base + 1, line_text=line)
        # execute the function body with local env seeded with call_args
        try:
            ret_val, out_lines, warn_add, inner_ops = self._execute_function(name, spec["block"], call_args, inputs, ops_scale)
        except EvalError as e:
            return i, 0, [], [], self._err("RUNTIME_ERROR", str(e), line=i + 1, column=1, line_text=line)
        # charge a function call op cost and accumulate any inner ops
        ops_delta = int(self.ops_map.get("func_call", 20) * ops_scale) + inner_ops
        out_add: List[str] = []
        if out_lines:
            out_add.extend(out_lines)
        if into_var:
            env[into_var] = ret_val
        else:
            # no 'into': print the return value if not None
            if ret_val is not None:
                out_add.append(str(ret_val))
        return i + 1, ops_delta, out_add, warn_add, None

    def _execute_function(
        self,
        name: str,
        block: List[str],
        args_env: Dict[str, Any],
        inputs: Dict[str, Any],
        ops_scale: float,
    ) -> Tuple[Any, List[str], List[str], int]:
        # Enforce call depth (prevent deep/recursive calls)
        if self._call_depth >= self.max_call_depth:
            raise EvalError("Call depth limit exceeded")
        self._call_depth += 1
        try:
            local_env: Dict[str, Any] = dict(args_env)
            out_lines: List[str] = []
            warn_add: List[str] = []
            ops_delta = 0
            i = 0
            steps_local = 0
            start_wall = time.time()
            while i < len(block):
                raw = block[i]
                if time.time() - start_wall > self.max_time_s:
                    raise EvalError("Time limit exceeded in function")
                if steps_local > self.max_steps:
                    warn_add.append("Step limit exceeded in function")
                    raise EvalError("Step limit exceeded in function")
                line = raw.strip()
                if not line or line.startswith("#"):
                    i += 1
                    continue
                # return handling
                if line.startswith("return ") or line == "return":
                    expr = line[len("return"):].strip()
                    if expr:
                        try:
                            val = eval_expr(expr, local_env)
                        except EvalError as e:
                            raise EvalError(str(e))
                    else:
                        val = None
                    return val, out_lines, warn_add, ops_delta
                steps_local += 1
                # charge small dispatch cost
                ops_delta += self.ops_map.get("other", 5)
                new_i, inner_ops, out_add, w_add, err = self._dispatch_statement(
                    block,
                    i,
                    line,
                    local_env,
                    inputs,
                    out_lines,
                    warn_add,
                    ops_delta,
                    ops_scale,
                )
                if err:
                    # propagate errors as EvalError inside function context
                    raise EvalError(err.get("message", "Function error"))
                if out_add:
                    for o in out_add:
                        if sum(len(x) for x in out_lines) + len(o) > self.max_output_chars:
                            raise EvalError("Output length limit reached in function")
                        out_lines.append(o)
                if w_add:
                    warn_add.extend(w_add)
                ops_delta += inner_ops
                i = new_i
            # implicit return None if no return seen
            return None, out_lines, warn_add, ops_delta
        finally:
            self._call_depth -= 1

    def _dispatch_ask(
        self,
        line: str,
        i: int,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        ops_scale: float,
    ) -> Tuple[
        int,
        int,
        List[str],
        List[str],
        Optional[Dict[str, Any]],
    ]:
        res = self._handle_ask(line, env, inputs, ops_scale)
        if res[4]:
            return i, 0, [], [], res[4]
        _, out_add, warn_add, ops_delta, _ = res
        return i + 1, ops_delta, out_add, warn_add, None

    def _dispatch_save_power(self, line: str, i: int, env: Dict[str, Any]):
        val = line[len("savePower ") :].strip()
        try:
            lvl = float(val)
        except Exception:
            return (
                i,
                0,
                [],
                [],
                {
                    "code": "SYNTAX_ERROR",
                    "message": "Invalid number for savePower",
                },
            )
        new_scale = max(0.1, 1.0 - (lvl * 0.01))
        # persist new ops scale into env for caller to pick up
        env["_ops_scale"] = new_scale
        return i + 1, 0, [], [f"savePower applied: level {lvl}"], None

    def _dispatch_control_if(
        self,
        lines: List[str],
        i: int,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        output_lines: List[str],
        warnings: List[str],
        total_ops: int,
        ops_scale: float,
    ):
        return self._handle_if(
            lines,
            i,
            env,
            inputs,
            output_lines,
            warnings,
            total_ops,
            ops_scale,
        )

    def _dispatch_control_repeat(
        self,
        lines: List[str],
        i: int,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        output_lines: List[str],
        warnings: List[str],
        total_ops: int,
        ops_scale: float,
    ):
        return self._handle_repeat(
            lines,
            i,
            env,
            inputs,
            output_lines,
            warnings,
            total_ops,
            ops_scale,
        )

    def _dispatch_control_while(
        self,
        lines: List[str],
        i: int,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        output_lines: List[str],
        warnings: List[str],
        total_ops: int,
        ops_scale: float,
    ):
        return self._handle_while(lines, i, env, inputs, output_lines, warnings, total_ops, ops_scale)

    def _dispatch_control_for(
        self,
        lines: List[str],
        i: int,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        output_lines: List[str],
        warnings: List[str],
        total_ops: int,
        ops_scale: float,
    ):
        return self._handle_for(lines, i, env, inputs, output_lines, warnings, total_ops, ops_scale)

    def _handle_while(
        self,
        lines: List[str],
        i: int,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        output_lines: List[str],
        warnings: List[str],
        total_ops: int,
        ops_scale: float,
    ):
        line = lines[i].strip()
        if not line.endswith(" then"):
            return i, 0, [], [], self._err(
                "SYNTAX_ERROR",
                "Expected 'then' after while condition",
                line=i + 1,
                column=len(line) + 1,
                line_text=lines[i],
                hint="Write: while <condition> then",
            )
        cond_expr = line[len("while "):-len(" then")].strip()
        try:
            block, end_idx = self._extract_block_for_run(lines, i + 1)
        except EvalError as e:
            return i, 0, [], [], self._err("SYNTAX_ERROR", str(e), line=i + 1, column=1, line_text=lines[i], hint="Add a matching 'end' for this 'while'.")

        out_add: List[str] = []
        warn_add: List[str] = []
        ops_delta = 0
        iterations = 0
        while True:
            # Evaluate condition in current env
            try:
                cond_val = eval_expr(cond_expr, env)
            except EvalError as e:
                base_col = 1 + len("while ")
                col = base_col + (e.column or 1) - 1
                return i, 0, [], [], self._err("RUNTIME_ERROR", str(e), line=i + 1, column=col, line_text=lines[i].strip(), hint="Fix the while condition.")
            if not bool(cond_val):
                break
            if iterations >= self.max_loop:
                warn_add.append(f"While iterations limited to {self.max_loop}")
                break
            if total_ops + ops_delta > self.max_steps:
                warn_add.append("Step limit exceeded inside while; aborted")
                break
            ops_delta += int(self.ops_map.get("loop_check", 5) * ops_scale)
            # Execute block inline so env mutations persist
            block_out, block_warns, block_ops, err = self._execute_block_inline(block, env, inputs, ops_scale)
            if err:
                return i, 0, [], [], err
            if block_out:
                out_add.extend(block_out)
            if block_warns:
                warn_add.extend(block_warns)
            ops_delta += block_ops
            iterations += 1
        return end_idx + 1, ops_delta, out_add, warn_add, None

    def _handle_for(
        self,
        lines: List[str],
        i: int,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        output_lines: List[str],
        warnings: List[str],
        total_ops: int,
        ops_scale: float,
    ):
        # Syntax: for name = start to end [step s]
        header = lines[i].strip()
        body = header[len("for "):].strip()
        if "=" not in body or " to " not in body:
            return i, 0, [], [], self._err(
                "SYNTAX_ERROR",
                "Use: for name = start to end [step s]",
                line=i + 1,
                column=1,
                line_text=lines[i],
            )
        name_part, rest = body.split("=", 1)
        varname = name_part.strip()
        if not varname.isidentifier():
            return i, 0, [], [], self._err("SYNTAX_ERROR", "Invalid loop variable name", line=i + 1, column=len("for ") + 1, line_text=lines[i])
        if " step " in rest:
            range_part, step_part = rest.split(" step ", 1)
        else:
            range_part, step_part = rest, None
        if " to " not in range_part:
            return i, 0, [], [], self._err("SYNTAX_ERROR", "Missing 'to' in for range", line=i + 1, column=1, line_text=lines[i])
        start_expr, end_expr = [s.strip() for s in range_part.split(" to ", 1)]
        try:
            start_val = eval_expr(start_expr, env)
            end_val = eval_expr(end_expr, env)
            step_val = eval_expr(step_part, env) if step_part else (1 if start_val <= end_val else -1)
        except EvalError as e:
            return i, 0, [], [], self._err("RUNTIME_ERROR", str(e), line=i + 1, column=1, line_text=lines[i])
        try:
            cur = float(start_val)
            endf = float(end_val)
            stepf = float(step_val)
            if stepf == 0:
                return i, 0, [], [], self._err("RUNTIME_ERROR", "for step cannot be 0", line=i + 1, column=1, line_text=lines[i])
        except Exception:
            return i, 0, [], [], self._err("RUNTIME_ERROR", "Invalid numeric values in for", line=i + 1, column=1, line_text=lines[i])
        try:
            block, end_idx = self._extract_block_for_run(lines, i + 1)
        except EvalError as e:
            return i, 0, [], [], self._err("SYNTAX_ERROR", str(e), line=i + 1, column=1, line_text=lines[i], hint="Add a matching 'end' for this 'for'.")

        out_add: List[str] = []
        warn_add: List[str] = []
        ops_delta = 0
        iterations = 0
        # Helper to check loop condition depending on step
        def cont(c: float) -> bool:
            return (c <= endf) if stepf > 0 else (c >= endf)
        while cont(cur):
            if iterations >= self.max_loop:
                warn_add.append(f"For iterations limited to {self.max_loop}")
                break
            if total_ops + ops_delta > self.max_steps:
                warn_add.append("Step limit exceeded inside for; aborted")
                break
            env[varname] = int(cur) if abs(cur - int(cur)) < 1e-9 else cur
            ops_delta += int(self.ops_map.get("loop_check", 5) * ops_scale)
            block_out, block_warns, block_ops, err = self._execute_block_inline(block, env, inputs, ops_scale)
            if err:
                return i, 0, [], [], err
            if block_out:
                out_add.extend(block_out)
            if block_warns:
                warn_add.extend(block_warns)
            ops_delta += block_ops
            iterations += 1
            cur += stepf
        return end_idx + 1, ops_delta, out_add, warn_add, None

    def _dispatch_simple_prefix(
        self,
        line: str,
        i: int,
        env: Dict[str, Any],
        ops_scale: float,
    ):
        """Handle simple 'say', 'let', 'warn' prefixes returning a small tuple.

        Returns (step_inc, ops_delta, out_add, warn_add, error_or_none).
        """
        if line.startswith("say "):
            res = self._handle_say(line, env, ops_scale)
            if res[4]:
                return i, 0, [], [], res[4]
            _, out_add, warn_add, ops_delta, _ = res
            return i + 1, ops_delta, out_add, warn_add, None
        if line.startswith("let "):
            res = self._handle_let(line, env, ops_scale)
            if res[4]:
                return i, 0, [], [], res[4]
            _, out_add, warn_add, ops_delta, _ = res
            return i + 1, ops_delta, out_add, warn_add, None
        if line.startswith("warn "):
            res = self._handle_warn(line, env, ops_scale)
            if res[4]:
                return i, 0, [], [], res[4]
            _, out_add, warn_add, ops_delta, _ = res
            return i + 1, ops_delta, out_add, warn_add, None
        return i, 0, [], [], None

    def _finalize_run(
        self,
        output_lines: List[str],
        warnings: List[str],
        total_ops: int,
        start_time: float,
    ) -> Dict[str, Any]:
        """Compute eco stats and produce final run result dict."""
        duration_s = max(0.000001, time.time() - start_time)
        eco = self._compute_eco(total_ops, duration_s)
        # re-add a runtime warning if usage is high
        if total_ops > 1000:
            warnings.append("High estimated energy use")
        return {
            "output": "\n".join(output_lines) + ("\n" if output_lines else ""),
            "warnings": warnings,
            "eco": eco,
            "errors": None,
        }

    def _dispatch_ecotip(
        self, total_ops: int, i: int, ops_scale: float
    ) -> Tuple[int, int, List[str], List[str], Optional[Dict[str, Any]]]:
        res = self._handle_ecotip(total_ops, ops_scale)
        if res[4]:
            return i, 0, [], [], res[4]
        _, out_add, warn_add, ops_delta, _ = res
        return i + 1, ops_delta, out_add, warn_add, None

    def _maybe_run_in_subprocess(self, settings: Dict[str, Any], code: str):
        # Run the provided code in a sandboxed subprocess. This isolates
        # potentially expensive or unsafe executions from the main process.
        try:
            rc, out, err = subprocess_runner.run_code_in_subprocess(
                code, timeout_s=int(settings.get("timeout_s", 2))
            )
        except Exception as e:
            return {
                "output": "",
                "warnings": [],
                "eco": None,
                "errors": {"code": "SUBPROCESS_ERROR", "message": str(e)},
            }
        if rc != 0:
            return {
                "output": out,
                "warnings": [],
                "eco": None,
                "errors": {"code": "SUBPROCESS_FAILED", "message": err},
            }
        try:
            payload = json.loads(out)
            return {
                "output": str(payload.get("result")),
                "warnings": [],
                "eco": None,
                "errors": payload.get("error"),
            }
        except Exception:
            return {
                "output": out,
                "warnings": [],
                "eco": None,
                "errors": None,
            }

    def _compute_eco(self, total_ops: int, duration_s: float) -> Dict[str, Any]:
        # compute a simple energy estimate based on operation counts and
        # a small runtime idle-power overhead. Units: Joules and kWh.
        compute_energy_J = total_ops * self.energy_per_op_J
        runtime_overhead_J = duration_s * self.idle_power_W
        total_energy_kWh = (compute_energy_J + runtime_overhead_J) / 3_600_000.0
        co2_g = total_energy_kWh * self.co2_per_kwh_g
        eco = {
            "total_ops": total_ops,
            "energy_J": compute_energy_J + runtime_overhead_J,
            "energy_kWh": total_energy_kWh,
            "co2_g": co2_g,
            "tips": [],
        }
        if total_ops > 1000:
            eco["tips"].append(
                "Consider reducing loop iterations or heavy math operations"
            )
        return eco


    def run(
        self,
        code: str,
        inputs: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Entry-point for running source text. We delegate heavy lifting to
        # `_prepare_and_execute` which handles subprocess fast-paths and
        # delegates to `_execute_core` for the main interpreter loop.
        output_lines, warnings, total_ops, maybe_err, start_time = (
            self._prepare_and_execute(code, inputs, settings)
        )
        if maybe_err.get("errors"):
            return {
                "output": "\n".join(output_lines),
                "warnings": warnings,
                "eco": None,
                "errors": maybe_err["errors"],
            }

        return self._finalize_run(output_lines, warnings, total_ops, start_time)

    def _prepare_and_execute(
        self,
        code: str,
        inputs: Optional[Dict[str, Any]],
        settings: Optional[Dict[str, Any]],
    ) -> Tuple[List[str], List[str], int, Dict[str, Any], float]:
        # thin wrapper: validation and delegation to core executor
        # normalize optionals into typed locals for mypy
        # Normalize optional arguments to concrete locals (helps static checks)
        inputs_local: Dict[str, Any] = inputs or {}
        settings_local: Dict[str, Any] = settings or {}

        # Subprocess fast-path: if the caller requested execution in an
        # isolated subprocess, forward to the subprocess helper which returns
        # a small result dict. This avoids the interpreter loop entirely.
        if settings_local.get("use_subprocess"):
            res = self._maybe_run_in_subprocess(settings_local, code)
            return (
                res.get("output", "").splitlines(),
                res.get("warnings", []),
                0,
                res.get("errors") or {},
                time.time(),
            )

        # otherwise run the normal in-process interpreter core
        return self._execute_core(code, inputs_local, settings_local)

    def _execute_core(
        self,
        code: str,
        inputs: Dict[str, Any],
        settings: Dict[str, Any],
        initial_env: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[str], List[str], int, Dict[str, Any], float]:
        """Core executor separated to reduce wrapper complexity.

        Returns (output_lines, warnings, total_ops, maybe_err, start_time).
        """
        # Core run loop: read lines, dispatch statements to handlers, enforce
        # budgets (time/steps/output) and collect operation counts and output.
        start_time = time.time()
        # seed environment from initial_env for nested interpreters
        env: Dict[str, Any] = dict(initial_env) if initial_env is not None else {}
        output_lines: List[str] = []
        warnings: List[str] = []
        total_ops = 0
        ops_scale = 1.0

        # Apply eco-related tunables from settings if present
        self.energy_per_op_J = settings.get("energy_per_op_J", self.energy_per_op_J)
        self.idle_power_W = settings.get("idle_power_W", self.idle_power_W)
        self.co2_per_kwh_g = settings.get("co2_per_kwh_g", self.co2_per_kwh_g)

        lines = code.splitlines()

        i = 0
        steps_local = 0
        start_wall = time.time()
        while i < len(lines):
            raw = lines[i]
            # enforce wall-clock timeout per-run
            if time.time() - start_wall > self.max_time_s:
                return output_lines, warnings, total_ops, {"errors": {"code": "TIMEOUT", "message": "Time limit exceeded"}}, start_time
            # enforce overall step budget (cheap check to avoid long loops)
            if steps_local > self.max_steps:
                # Record a human-readable warning in addition to the structured
                # STEP_LIMIT error so callers and tests can surface both forms.
                warnings.append("Step limit exceeded")
                return output_lines, warnings, total_ops, {"errors": {"code": "STEP_LIMIT", "message": "Step limit exceeded"}}, start_time
            line = raw.strip()
            if not line or line.startswith("#"):
                i += 1
                continue
            steps_local += 1
            ops_scale_local = env.get("_ops_scale", ops_scale)
            # charge a small 'other' op cost for the dispatch itself
            total_ops += self.ops_map.get("other", 5)
            # keep ecoOps() in sync
            env["_eco_ops"] = total_ops
            new_i, ops_delta, out_add, warn_add, err = self._dispatch_statement(
                lines,
                i,
                line,
                env,
                inputs,
                output_lines,
                warnings,
                total_ops,
                ops_scale_local,
            )
            if err:
                # handlers return structured error dicts which the API surfaces
                return output_lines, warnings, total_ops, {"errors": err}, start_time
            if out_add:
                # enforce output length cap incrementally to avoid large memory
                # usage and to provide an early OUTPUT_LIMIT error if exceeded.
                for o in out_add:
                    if sum(len(x) for x in output_lines) + len(o) > self.max_output_chars:
                        return output_lines, warnings, total_ops, {"errors": {"code": "OUTPUT_LIMIT", "message": "Output length limit reached"}}, start_time
                    output_lines.append(o)
            if warn_add:
                warnings.extend(warn_add)
            total_ops += ops_delta
            i = new_i
        return output_lines, warnings, total_ops, {}, start_time

