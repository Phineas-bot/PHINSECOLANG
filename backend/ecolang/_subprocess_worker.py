"""Worker script executed in a subprocess to evaluate a restricted
piece of code.

Protocol: read JSON from stdin {"code": "..."}, execute in restricted
globals, and print JSON to stdout {"result": ..., "error": ...}
"""
import ast
import json
import sys
from typing import Any, Dict, Optional, Tuple


def safe_exec(code_str: str) -> Tuple[Optional[Any], Optional[str]]:
    # Very small sandbox: only allow expressions and print via a captured output.
    # For now, we'll eval expressions; do not use in production for untrusted code.
    try:
        node = ast.parse(code_str, mode='exec')
    except Exception as e:
        return None, f'parse_error: {e}'

    # Disallow import and attribute access nodes for basic safety
    for n in ast.walk(node):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            return None, 'imports not allowed'
        if isinstance(n, ast.Attribute):
            return None, 'attribute access not allowed'

    # Run the code in a minimal namespace
    g: Dict[str, Any] = {"__builtins__": {}}
    local_ns: Dict[str, Any] = {}
    try:
        exec(compile(node, '<string>', 'exec'), g, local_ns)
        return local_ns.get('result', None), None
    except Exception as e:
        return None, f'error: {e}'


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
        code = payload.get('code', '')
    except Exception as e:
        print(json.dumps({'result': None, 'error': f'bad_payload: {e}'}))
        sys.exit(1)

    res, err = safe_exec(code)
    print(json.dumps({'result': res, 'error': err}))


if __name__ == '__main__':
    main()
