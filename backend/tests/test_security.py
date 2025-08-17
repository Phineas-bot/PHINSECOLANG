"""Security-oriented tests ensuring dangerous constructs are rejected."""

from backend.ecolang.interpreter import Interpreter, EvalError


def test_disallow_call_in_expr():
    it = Interpreter()
    res = it.run('say (1 + 2)')
    assert res['errors'] is None


def test_disallow_exec_in_expr():
    it = Interpreter()
    res = it.run('say __import__("os")')
    # Expect a runtime/syntax error due to disallowed name
    assert res['errors'] is not None


def test_subprocess_worker_disallows_imports():
    # ensure subprocess worker rejects imports
    from backend.ecolang._subprocess_worker import safe_exec

    result, err = safe_exec('import os')
    assert err is not None
