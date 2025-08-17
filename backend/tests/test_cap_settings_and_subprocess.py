"""Unit tests for server-side caps and subprocess worker contract.

This module contains two focused tests:
- `test_cap_settings_clamps`: ensures the FastAPI `_cap_settings` helper
  clamps client-provided values to server-side Interpreter defaults.
- `test_subprocess_worker_contract`: ensures the subprocess runner/worker
  follow the JSON-over-stdin/stdout contract and successfully returns a
  simple `result` value for well-formed code.

These tests are small and fast and do not require network access.
"""

import json

from backend.app.main import _cap_settings
from backend.ecolang.subprocess_runner import run_code_in_subprocess
from backend.ecolang.interpreter import Interpreter


def test_cap_settings_clamps():
    """Providing overly-large settings must be clamped to Interpreter defaults.

    We create an unrealistic 'settings' dict with values larger than the
    defaults and assert `_cap_settings` lowers them to the Interpreter's
    safe defaults.
    """
    # pick absurdly large client-supplied values
    requested = {
        "max_steps": 10_000_000,
        "max_loop": 1_000_000,
        "max_time_s": 10_000.0,
        "max_output_chars": 10_000_000,
        # eco tunables should pass through (they're not safety-critical)
        "energy_per_op_J": 0.0001,
        "idle_power_W": 0.5,
        "co2_per_kwh_g": 400.0,
    }

    capped = _cap_settings(requested)
    defaults = Interpreter()

    # assert numeric safety caps are no greater than defaults
    assert capped["max_steps"] <= defaults.max_steps
    assert capped["max_loop"] <= defaults.max_loop
    assert capped["max_time_s"] <= defaults.max_time_s
    assert capped["max_output_chars"] <= defaults.max_output_chars

    # eco tunables propagate (we don't strictly clamp them here)
    assert capped["energy_per_op_J"] == float(requested["energy_per_op_J"])
    assert capped["idle_power_W"] == float(requested["idle_power_W"])
    assert capped["co2_per_kwh_g"] == float(requested["co2_per_kwh_g"])


def test_subprocess_worker_contract():
    """Run a tiny piece of code in the subprocess worker and validate JSON.

    The worker returns JSON with keys `result` and `error`. We send code
    that assigns `result = 12345` and expect a zero return code and no
    reported error.
    """
    code = """
result = 12345
"""

    rc, out, err = run_code_in_subprocess(code, timeout_s=2)
    assert rc == 0, f"subprocess returned non-zero rc: {rc}, stderr: {err}"

    # parse worker JSON output
    j = json.loads(out)
    assert "result" in j and "error" in j
    assert j["error"] is None
    assert j["result"] == 12345
