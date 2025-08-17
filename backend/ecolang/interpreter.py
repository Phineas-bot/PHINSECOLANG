import ast
import json
import time
from typing import Any, Dict, List, Tuple, Optional

from . import subprocess_runner


# Simple interpreter prototype supporting `say` and `let` plus expressions.
class EvalError(Exception):
    pass


class SafeEvaluator(ast.NodeVisitor):
    def __init__(self, env: Dict[str, Any]):
        self.env = env

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
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
        raise EvalError("Unsupported unary op")

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
        raise EvalError("Function calls are not allowed in EcoLang")

    def generic_visit(self, node):
        raise EvalError(f"Unsupported expression: {type(node).__name__}")


def eval_expr(expr: str, env: Dict[str, Any]):
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise EvalError(f"Syntax error in expression: {expr}") from e
    evaluator = SafeEvaluator(env)
    return evaluator.visit(tree)


class Interpreter:
    def __init__(self):
        # Default tunables from spec
        self.ops_map = {
            "print": 50,
            "loop_check": 5,
            "math": 10,
            "assign": 5,
            "io": 200,
            "optimize": 1000,
            "other": 5,
        }
        self.energy_per_op_J = 1e-9
        self.idle_power_W = 0.5
        self.co2_per_kwh_g = 475
        # limits
        self.max_steps = 100000
        self.max_output_chars = 5000

    def _run_sub_interpreter(
        self,
        code: str,
        inputs: Dict[str, Any],
        settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run a fresh Interpreter for nested blocks to preserve state.

        The original implementation used Interpreter().run directly; this
        helper keeps the behaviour but centralizes the call site.
        """
        return Interpreter().run(code, inputs=inputs, settings=settings)

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
    ) -> Tuple[int, int, List[str], List[str], Optional[Dict[str, Any]]]:
        """Evaluate an if/then/else block starting at index i.

        Returns (new_i, output_lines_add, warnings_add, total_ops_delta, error_or_none)
        """
        line = lines[i].strip()
        cond_expr = line[3:-5].strip()
        try:
            block, end_idx = self._extract_block_for_run(lines, i + 1)
        except EvalError as e:
            return (
                end_idx if "end_idx" in locals() else i,
                0,
                [],
                [],
                {"code": "SYNTAX_ERROR", "message": str(e)},
            )

        # find optional else inside block (top-level)
        else_idx = None
        depth = 0
        for j, r in enumerate(block):
            t = r.strip()
            if t.startswith("if ") or t.startswith("repeat "):
                depth += 1
                continue
            if t == "end":
                if depth > 0:
                    depth -= 1
                continue
            if t == "else" and depth == 0:
                else_idx = j
                break
        try:
            cond_val = eval_expr(cond_expr, env)
        except EvalError as e:
            return (i, 0, [], [], {"code": "RUNTIME_ERROR", "message": str(e)})

        if bool(cond_val):
            exec_block = block[:else_idx] if else_idx is not None else block
        else:
            exec_block = block[else_idx + 1 :] if else_idx is not None else []

        sub_code = "\n".join(exec_block)
        sub_res = self._run_sub_interpreter(
            sub_code,
            inputs=inputs,
            settings={
                "energy_per_op_J": self.energy_per_op_J,
                "idle_power_W": self.idle_power_W,
                "co2_per_kwh_g": self.co2_per_kwh_g,
            },
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
    ) -> Tuple[int, int, List[str], List[str], Optional[Dict[str, Any]]]:
        """Evaluate a repeat N times block starting at index i.

        Returns (new_i, output_lines_add, warnings_add, total_ops_delta, error_or_none)
        """
        line = lines[i].strip()
        mid = line[len("repeat ") : -len(" times")].strip()
        try:
            n = int(mid)
        except Exception:
            return (
                i,
                0,
                [],
                [],
                {"code": "SYNTAX_ERROR", "message": "Invalid repeat count"},
            )
        try:
            block, end_idx = self._extract_block_for_run(lines, i + 1)
        except EvalError as e:
            return (i, 0, [], [], {"code": "SYNTAX_ERROR", "message": str(e)})

        sub_code = "\n".join(block)
        out_add: List[str] = []
        warn_add: List[str] = []
        ops_delta = 0
        for _ in range(n):
            if total_ops + ops_delta > self.max_steps:
                warn_add.append("Step limit exceeded inside repeat; aborted")
                break
            ops_delta += int(self.ops_map.get("loop_check", 5) * ops_scale)
            sub_res = self._run_sub_interpreter(
                sub_code,
                inputs=inputs,
                settings={
                    "energy_per_op_J": self.energy_per_op_J,
                    "idle_power_W": self.idle_power_W,
                    "co2_per_kwh_g": self.co2_per_kwh_g,
                },
            )
            if sub_res.get("errors"):
                return (i, 0, [], [], sub_res)
            if sub_res.get("output"):
                out_add.extend(sub_res["output"].splitlines())
            warn_add.extend(sub_res.get("warnings", []))
            ops_delta += sub_res.get("eco", {}).get("total_ops", 0)
        return (end_idx + 1, ops_delta, out_add, warn_add, None)

    def _find_else_index(self, block: List[str]) -> Optional[int]:
        depth = 0
        for j, r in enumerate(block):
            t = r.strip()
            if t.startswith("if ") or t.startswith("repeat "):
                depth += 1
                continue
            if t == "end":
                if depth > 0:
                    depth -= 1
                continue
            if t == "else" and depth == 0:
                return j
        return None  # type: ignore

    def _handle_say(self, line: str, env: Dict[str, Any], ops_scale: float) -> Tuple[Optional[int], List[str], List[str], int, Optional[Dict[str, Any]]]:
        expr = line[4:].strip()
        try:
            val = eval_expr(expr, env)
        except EvalError as e:
            return (None, [], [], 0, {"code": "RUNTIME_ERROR", "message": str(e)})
        output = str(val)
        ops_delta = int(self.ops_map.get("print", 50) * ops_scale)
        return (1, [output], [], ops_delta, None)

    def _handle_let(self, line: str, env: Dict[str, Any], ops_scale: float) -> Tuple[Optional[int], List[str], List[str], int, Optional[Dict[str, Any]]]:
        rest = line[4:].strip()
        if "=" not in rest:
            return (
                None,
                [],
                [],
                0,
                {"code": "SYNTAX_ERROR", "message": "Expected '=' in let statement"},
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
                {"code": "SYNTAX_ERROR", "message": "Invalid identifier in let"},
            )
        try:
            val = eval_expr(expr, env)
        except EvalError as e:
            return (None, [], [], 0, {"code": "RUNTIME_ERROR", "message": str(e)})
        env[name] = val
        ops_delta = int(self.ops_map.get("assign", 5) * ops_scale)
        return (1, [], [], ops_delta, None)

    def _handle_ask(
        self,
        line: str,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        ops_scale: float,
    ) -> Tuple[Optional[int], List[str], List[str], int, Optional[Dict[str, Any]]]:
        name = line[4:].strip()
        if not name.isidentifier():
            return (
                None,
                [],
                [],
                0,
                {"code": "SYNTAX_ERROR", "message": "Invalid identifier in ask"},
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

    def _handle_warn(self, line: str, env: Dict[str, Any], ops_scale: float) -> Tuple[Optional[int], List[str], List[str], int, Optional[Dict[str, Any]]]:
        expr = line[5:].strip()
        try:
            val = eval_expr(expr, env)
        except EvalError as e:
            return (None, [], [], 0, {"code": "RUNTIME_ERROR", "message": str(e)})
        warn = str(val)
        ops_delta = int(self.ops_map.get("other", 5) * ops_scale)
        return (1, [], [warn], ops_delta, None)

    def _handle_ecotip(self, total_ops: int, ops_scale: float) -> Tuple[int, List[str], List[str], int, Optional[Dict[str, Any]]]:
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
            if txt.startswith("if ") or txt.startswith("repeat "):
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
    ) -> Tuple[int, int, List[str], List[str], Optional[Dict[str, Any]]]:
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

        dispatch_map = {
            "say": lambda: self._dispatch_simple_prefix(
                line, i, env, ops_scale
            ),
            "let": lambda: self._dispatch_simple_prefix(
                line, i, env, ops_scale
            ),
            "warn": lambda: self._dispatch_simple_prefix(
                line, i, env, ops_scale
            ),
            "ask": lambda: self._dispatch_ask(
                line, i, env, inputs, ops_scale
            ),
            "if": lambda: self._dispatch_control_if(
                lines, i, env, inputs, output_lines, warnings, total_ops, ops_scale
            ),
            "repeat": lambda: self._dispatch_control_repeat(
                lines, i, env, inputs, output_lines, warnings, total_ops, ops_scale
            ),
        }

        handler = dispatch_map.get(token)
        if not handler:
            return (
                i,
                0,
                [],
                [],
                {"code": "SYNTAX_ERROR", "message": f"Unknown statement: {line}"},
            )
        res = handler()
        if not res:
            return (
                i,
                0,
                [],
                [],
                {"code": "SYNTAX_ERROR", "message": f"Unknown statement: {line}"},
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
            return i, 0, [], [], err
        return new_i, ops_delta, out_add, warn_add, None

    def _dispatch_ask(
        self,
        line: str,
        i: int,
        env: Dict[str, Any],
        inputs: Dict[str, Any],
        ops_scale: float,
    ) -> Tuple[int, int, List[str], List[str], Optional[Dict[str, Any]]]:
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

    def _dispatch_ecotip(self, total_ops: int, i: int, ops_scale: float) -> Tuple[int, int, List[str], List[str], Optional[Dict[str, Any]]]:
        res = self._handle_ecotip(total_ops, ops_scale)
        if res[4]:
            return i, 0, [], [], res[4]
        _, out_add, warn_add, ops_delta, _ = res
        return i + 1, ops_delta, out_add, warn_add, None

    def _maybe_run_in_subprocess(self, settings: Dict[str, Any], code: str):
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
        self, code: str, inputs: Optional[Dict[str, Any]], settings: Optional[Dict[str, Any]]
    ) -> Tuple[List[str], List[str], int, Dict[str, Any], float]:
        # thin wrapper: validation and delegation to core executor
        # normalize optionals into typed locals for mypy
        inputs_local: Dict[str, Any] = inputs or {}
        settings_local: Dict[str, Any] = settings or {}

        # handle subprocess fast-path
        if settings_local.get("use_subprocess"):
            res = self._maybe_run_in_subprocess(settings_local, code)
            return (
                res.get("output", "").splitlines(),
                res.get("warnings", []),
                0,
                res.get("errors") or {},
                time.time(),
            )

        # otherwise delegate heavy work using typed locals
        return self._execute_core(code, inputs_local, settings_local)

    def _execute_core(
        self, code: str, inputs: Dict[str, Any], settings: Dict[str, Any]
    ) -> Tuple[List[str], List[str], int, Dict[str, Any], float]:
        """Core executor separated to reduce wrapper complexity.

        Returns (output_lines, warnings, total_ops, maybe_err, start_time).
        """
        start_time = time.time()
        env: Dict[str, Any] = {}
        output_lines: List[str] = []
        warnings: List[str] = []
        total_ops = 0
        ops_scale = 1.0

        # apply settings
        self.energy_per_op_J = settings.get("energy_per_op_J", self.energy_per_op_J)
        self.idle_power_W = settings.get("idle_power_W", self.idle_power_W)
        self.co2_per_kwh_g = settings.get("co2_per_kwh_g", self.co2_per_kwh_g)

        lines = code.splitlines()

        i = 0
        steps_local = 0
        while i < len(lines):
            raw = lines[i]
            if steps_local > self.max_steps:
                warnings.append("Step limit exceeded; execution aborted")
                break
            line = raw.strip()
            if not line or line.startswith("#"):
                i += 1
                continue
            steps_local += 1
            ops_scale_local = env.get("_ops_scale", ops_scale)
            total_ops += self.ops_map.get("other", 5)
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
                return output_lines, warnings, total_ops, {"errors": err}, start_time
            if out_add:
                output_lines.extend(out_add)
            if warn_add:
                warnings.extend(warn_add)
            total_ops += ops_delta
            i = new_i
        return output_lines, warnings, total_ops, {}, start_time

