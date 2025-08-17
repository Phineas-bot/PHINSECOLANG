"""Helpers to run a small, controlled subprocess worker for code execution.

This module provides `run_code_in_subprocess`, a convenience wrapper that
launches the `_subprocess_worker.py` helper (which follows a simple
JSON-over-stdin/stdout protocol). The function enforces a wall-clock timeout
and returns the raw subprocess outputs for higher-level handling.

Note: the returned stdout is the worker's JSON string; callers should parse
and validate it before trusting its contents.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Tuple


def run_code_in_subprocess(code: str, timeout_s: int = 2) -> Tuple[int, str, str]:
    """Run the given code string in a short-lived subprocess.

    Returns a tuple (returncode, stdout, stderr). stdout contains the JSON
    response emitted by the worker (or an empty string). stderr contains any
    stderr produced by the worker process. A returncode of -1 indicates the
    process was killed due to timeout.
    """
    runner_path = Path(__file__).parent / "_subprocess_worker.py"
    if not runner_path.exists():
        raise FileNotFoundError(str(runner_path))

    proc = subprocess.Popen(
        [sys.executable, str(runner_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # send code as JSON according to the worker protocol
    payload = json.dumps({"code": code})
    try:
        out, err = proc.communicate(payload, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        return -1, "", "TIMEOUT"
    return proc.returncode, out or "", err or ""
