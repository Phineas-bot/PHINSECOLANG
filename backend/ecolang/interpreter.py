import time
import ast
from typing import Dict, Any, Tuple, List

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
        left = self.visit(node.left)
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise EvalError("Chained comparisons not supported")
        op = node.ops[0]
        right = self.visit(node.comparators[0])
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
        if node.id == 'true':
            return True
        if node.id == 'false':
            return False
        raise EvalError(f"Undefined variable '{node.id}'")

    def visit_Call(self, node):
        raise EvalError("Function calls are not allowed in EcoLang")

    def generic_visit(self, node):
        raise EvalError(f"Unsupported expression: {type(node).__name__}")


def eval_expr(expr: str, env: Dict[str, Any]):
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as e:
        raise EvalError(f"Syntax error in expression: {expr}")
    evaluator = SafeEvaluator(env)
    return evaluator.visit(tree)


class Interpreter:
    def __init__(self):
        # Default tunables from spec
        self.ops_map = { 'print':50, 'loop_check':5, 'math':10, 'assign':5, 'io':200, 'optimize':1000, 'other':5 }
        self.energy_per_op_J = 1e-9
        self.idle_power_W = 0.5
        self.co2_per_kwh_g = 475
        # limits
        self.max_steps = 100000
        self.max_output_chars = 5000

    def run(self, code: str, inputs: Dict[str, Any]={}, settings: Dict[str, Any]={}) -> Dict[str, Any]:
        start_time = time.time()
        env: Dict[str, Any] = {}
        output_lines: List[str] = []
        warnings: List[str] = []
        steps = 0
        total_ops = 0
        ops_scale = 1.0

        # apply settings
        self.energy_per_op_J = settings.get('energy_per_op_J', self.energy_per_op_J)
        self.idle_power_W = settings.get('idle_power_W', self.idle_power_W)
        self.co2_per_kwh_g = settings.get('co2_per_kwh_g', self.co2_per_kwh_g)

        lines = code.splitlines()

        def extract_block(start_idx: int) -> Tuple[List[str], int]:
            """Extract lines until matching 'end', handling nested blocks.
            Returns (block_lines, index_of_end_line).
            """
            block = []
            depth = 0
            i = start_idx
            while i < len(lines):
                raw = lines[i]
                txt = raw.strip()
                # track nested starts
                if txt.startswith('if ') or txt.startswith('repeat '):
                    depth += 1
                    block.append(raw)
                elif txt == 'end':
                    if depth == 0:
                        return block, i
                    else:
                        depth -= 1
                        block.append(raw)
                else:
                    block.append(raw)
                i += 1
            # if we reach here, unmatched block
            raise EvalError('Missing end for block')

        i = 0
        while i < len(lines):
            raw = lines[i]
            if steps > self.max_steps:
                warnings.append('Step limit exceeded; execution aborted')
                break
            line = raw.strip()
            # ignore comments and blank lines
            if not line or line.startswith('#'):
                i += 1
                continue

            # increment for statement dispatch
            steps += 1
            total_ops += self.ops_map.get('other', 5)

            # SAY
            if line.startswith('say '):
                expr = line[4:].strip()
                try:
                    val = eval_expr(expr, env)
                except EvalError as e:
                    return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"RUNTIME_ERROR","message":str(e)}}
                output = str(val)
                output_lines.append(output)
                total_ops += int(self.ops_map.get('print',50) * ops_scale)
                # enforce max output length
                if sum(len(l) for l in output_lines) > self.max_output_chars:
                    warnings.append('Output truncated (too long)')
                    break
                i += 1
                continue

            # LET
            if line.startswith('let '):
                rest = line[4:].strip()
                if '=' not in rest:
                    return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"SYNTAX_ERROR","message":"Expected '=' in let statement"}}
                name, expr = rest.split('=', 1)
                name = name.strip()
                expr = expr.strip()
                if not name.isidentifier():
                    return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"SYNTAX_ERROR","message":"Invalid identifier in let"}}
                try:
                    val = eval_expr(expr, env)
                except EvalError as e:
                    return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"RUNTIME_ERROR","message":str(e)}}
                env[name] = val
                total_ops += int(self.ops_map.get('assign',5) * ops_scale)
                i += 1
                continue

            # ASK
            if line.startswith('ask '):
                name = line[4:].strip()
                if not name.isidentifier():
                    return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"SYNTAX_ERROR","message":"Invalid identifier in ask"}}
                if name in inputs:
                    env[name] = inputs[name]
                else:
                    return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"RUNTIME_ERROR","message":f"Missing input for '{name}'"}}
                total_ops += int(self.ops_map.get('io',200) * ops_scale)
                i += 1
                continue

            # WARN
            if line.startswith('warn '):
                expr = line[5:].strip()
                try:
                    val = eval_expr(expr, env)
                except EvalError as e:
                    return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"RUNTIME_ERROR","message":str(e)}}
                warnings.append(str(val))
                total_ops += int(self.ops_map.get('other',5) * ops_scale)
                i += 1
                continue

            # ECOTIP
            if line == 'ecoTip':
                tips = [
                    'Turn off unused devices',
                    'Reduce loop counts',
                    'Prefer simpler math operations'
                ]
                tip = tips[total_ops % len(tips)]
                output_lines.append(f"ecoTip: {tip}")
                i += 1
                total_ops += int(self.ops_map.get('other',5) * ops_scale)
                continue

            # SAVEPOWER
            if line.startswith('savePower '):
                val = line[len('savePower '):].strip()
                try:
                    lvl = float(val)
                except Exception:
                    return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"SYNTAX_ERROR","message":"Invalid number for savePower"}}
                # apply a simple ops scaling: more savePower => smaller ops cost (demo)
                ops_scale = max(0.1, 1.0 - (lvl * 0.01))
                warnings.append(f"savePower applied: level {lvl}")
                i += 1
                continue

            # IF ... THEN ... (optional ELSE) ... END
            if line.startswith('if ') and line.endswith(' then'):
                cond_expr = line[3:-5].strip()
                # extract block after this line
                try:
                    block, end_idx = extract_block(i+1)
                except EvalError as e:
                    return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"SYNTAX_ERROR","message":str(e)}}
                # find optional else inside block (top-level)
                else_idx = None
                depth = 0
                for j, r in enumerate(block):
                    t = r.strip()
                    if t.startswith('if ') or t.startswith('repeat '):
                        depth += 1
                    elif t == 'end':
                        if depth > 0:
                            depth -= 1
                    elif t == 'else' and depth == 0:
                        else_idx = j
                        break
                try:
                    cond_val = eval_expr(cond_expr, env)
                except EvalError as e:
                    return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"RUNTIME_ERROR","message":str(e)}}
                if bool(cond_val):
                    exec_block = block[:else_idx] if else_idx is not None else block
                else:
                    exec_block = block[else_idx+1:] if else_idx is not None else []
                # execute the chosen block lines (simple recursive evaluation)
                sub_code = "\n".join(exec_block)
                # recursion: run on sub_code but preserve env, collect outputs
                sub_res = Interpreter().run(sub_code, inputs=inputs, settings={'energy_per_op_J': self.energy_per_op_J, 'idle_power_W': self.idle_power_W, 'co2_per_kwh_g': self.co2_per_kwh_g})
                # merge sub results
                if sub_res.get('errors'):
                    return sub_res
                if sub_res.get('output'):
                    output_lines.extend(sub_res['output'].splitlines())
                warnings.extend(sub_res.get('warnings', []))
                total_ops += sub_res.get('eco', {}).get('total_ops', 0)
                i = end_idx + 1
                continue

            # REPEAT N times ... END
            if line.startswith('repeat ' ) and line.endswith(' times'):
                mid = line[len('repeat '):-len(' times')].strip()
                try:
                    n = int(mid)
                except Exception:
                    return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"SYNTAX_ERROR","message":"Invalid repeat count"}}
                try:
                    block, end_idx = extract_block(i+1)
                except EvalError as e:
                    return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"SYNTAX_ERROR","message":str(e)}}
                sub_code = "\n".join(block)
                # run the block n times
                for k in range(n):
                    if steps > self.max_steps:
                        warnings.append('Step limit exceeded inside repeat; aborted')
                        break
                    total_ops += int(self.ops_map.get('loop_check',5) * ops_scale)
                    sub_res = Interpreter().run(sub_code, inputs=inputs, settings={'energy_per_op_J': self.energy_per_op_J, 'idle_power_W': self.idle_power_W, 'co2_per_kwh_g': self.co2_per_kwh_g})
                    if sub_res.get('errors'):
                        return sub_res
                    if sub_res.get('output'):
                        output_lines.extend(sub_res['output'].splitlines())
                    warnings.extend(sub_res.get('warnings', []))
                    total_ops += sub_res.get('eco', {}).get('total_ops', 0)
                i = end_idx + 1
                continue

            # unknown statement
            return {"output": "\n".join(output_lines), "warnings": warnings, "eco": None, "errors": {"code":"SYNTAX_ERROR","message":f"Unknown statement: {line}"}}

        duration_s = max(0.000001, time.time() - start_time)
        # compute eco stats
        compute_energy_J = total_ops * self.energy_per_op_J
        runtime_overhead_J = duration_s * self.idle_power_W
        total_energy_kWh = (compute_energy_J + runtime_overhead_J) / 3_600_000.0
        co2_g = total_energy_kWh * self.co2_per_kwh_g

        eco = {
            'total_ops': total_ops,
            'energy_J': compute_energy_J + runtime_overhead_J,
            'energy_kWh': total_energy_kWh,
            'co2_g': co2_g,
            'tips': []
        }
        # simple tip
        if total_ops > 1000:
            eco['tips'].append('Consider reducing loop iterations or heavy math operations')
            warnings.append('High estimated energy use')

        return {"output": "\n".join(output_lines) + ("\n" if output_lines else ""), "warnings": warnings, "eco": eco, "errors": None}
