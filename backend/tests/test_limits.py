"""Tests for interpreter runtime limits (time, steps, output caps)."""

from backend.ecolang.interpreter import Interpreter


def test_step_limit():
    it = Interpreter()
    it.max_steps = 5
    code = "\n".join(["say 1"] * 20)
    res = it.run(code)
    assert res["errors"] and res["errors"]["code"] in ("STEP_LIMIT", "TIMEOUT")


def test_loop_cap():
    it = Interpreter()
    it.max_loop = 3
    code = "repeat 10 times\n    say 1\nend"
    res = it.run(code)
    assert any("Repeat count limited" in w for w in res["warnings"]) or (res["errors"] is not None)


def test_output_limit():
    it = Interpreter()
    it.max_output_chars = 10
    code = "\n".join(["say \"abcdefghij\""] * 5)
    res = it.run(code)
    assert res["errors"] and res["errors"]["code"] == "OUTPUT_LIMIT"
