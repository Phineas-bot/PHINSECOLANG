import json
import subprocess
import sys
from pathlib import Path
from typing import Tuple


def run_code_in_subprocess(code: str, timeout_s: int = 2) -> Tuple[int, str, str]:
    """Run the given code string in a short-lived subprocess.

    Returns: (returncode, stdout, stderr)
    The subprocess runs a small runner script that executes the code under json-wrapped protocol.
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
    # send code as JSON
    payload = json.dumps({"code": code})
    try:
        out, err = proc.communicate(payload, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        return -1, "", "TIMEOUT"
    return proc.returncode, out or "", err or ""
