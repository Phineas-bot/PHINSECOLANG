"""Subprocess worker for executing a tiny, restricted piece of Python code.

This script is intended to be executed as a short-lived subprocess. It reads
a single JSON object from stdin with shape {"code": "..."}, attempts to
execute the code in a deliberately minimal namespace, and writes a JSON
response to stdout with shape {"result": ..., "error": ...}.

Security and limitations:
  - This is a very small, conservative sandbox. It disallows many AST node
    types (imports, attribute access, calls, subscripts, definitions). It
    intentionally *does not* provide a full OS-level sandbox and should not be
    used to run fully untrusted code in production without additional
    containment (namespaces, user isolation, seccomp, containers, etc.).
  - The calling process should enforce wall-clock timeouts and resource caps.
"""

import ast
import json
import sys
from typing import Any, Dict, Optional, Tuple


def safe_exec(code_str: str) -> Tuple[Optional[Any], Optional[str]]:
    """Parse and execute code with a tiny AST-based whitelist.

    Returns (result, error_str). `result` is taken from a `result` name in the
    executed locals if present. `error_str` is None on success or a short
    textual description on failure.
    """
    # Parse once and reject parse errors early
    try:
        node = ast.parse(code_str, mode='exec')
    except Exception as e:
        return None, f'parse_error: {e}'

    # Disallow nodes we consider unsafe for this tiny sandbox. This is a blunt
    # instrument: keep the list minimal and easy to understand.
    for n in ast.walk(node):
        if isinstance(n, (ast.Import, ast.ImportFrom, ast.Attribute, ast.Call, ast.Subscript, ast.Lambda, ast.FunctionDef, ast.ClassDef)):
            return None, f'{type(n).__name__} not allowed'
        # Disallow direct use of dangerous builtins or names
        if isinstance(n, ast.Name) and n.id in ("__import__", "eval", "exec", "open", "os", "sys"):
            return None, f'name {n.id} not allowed'

    # Minimal globals: no builtins provided. The caller must ensure this worker
    # is invoked in a controlled environment with external timeouts.
    g: Dict[str, Any] = {"__builtins__": {}}
    local_ns: Dict[str, Any] = {}
    try:
        exec(compile(node, '<string>', 'exec'), g, local_ns)
        # If the executed code set a `result` variable we return it
        return local_ns.get('result', None), None
    except Exception as e:
        return None, f'error: {e}'


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
        code = payload.get('code', '')
    except Exception as e:
        # Communicate payload decoding errors via JSON to the parent process
        print(json.dumps({'result': None, 'error': f'bad_payload: {e}'}))
        sys.exit(1)

    res, err = safe_exec(code)
    print(json.dumps({'result': res, 'error': err}))


if __name__ == '__main__':
    main()
