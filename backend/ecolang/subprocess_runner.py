"""Helpers to run a small, controlled subprocess worker for code execution.

This module provides `run_code_in_subprocess`, a convenience wrapper that
launches the `_subprocess_worker.py` helper (which follows a simple
JSON-over-stdin/stdout protocol). The function enforces a wall-clock timeout
and can apply light OS-level resource limits on POSIX systems (CPU seconds
and address-space / memory usage) to reduce the blast radius of buggy code.

Behavior and guarantees:
  - On POSIX, optional RLIMIT_CPU and RLIMIT_AS limits are applied using a
    preexec function. On Windows these limits are no-ops.
  - The worker is launched as a short-lived process with closed file
    descriptors and a minimal environment by default.
  - The function returns (returncode, stdout, stderr). A returncode of -1
    indicates the process was terminated due to timeout.

Note: This is not a substitute for proper container/VM-based isolation in
production. It reduces risk in CI and test environments.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple, Optional


def _make_posix_preexec(cpu_seconds: Optional[int], mem_limit_mb: Optional[int]):
    """Return a preexec_fn that applies resource limits on POSIX systems.

    The returned function is safe to attach to `subprocess.Popen(...,
    preexec_fn=...)`. If the `resource` module is unavailable the function
    silently becomes a no-op.
    """
    def preexec():
        try:
            import resource

            # Limit CPU time (seconds)
            if cpu_seconds is not None:
                resource.setrlimit(resource.RLIMIT_CPU, (int(cpu_seconds), int(cpu_seconds)))

            # Limit address space (virtual memory) in bytes
            if mem_limit_mb is not None:
                mem_bytes = int(mem_limit_mb) * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

            # Start a new session to isolate signals
            try:
                os.setsid()
            except Exception:
                # not critical; continue
                pass
        except Exception:
            # If resource isn't available (e.g., on Windows), silently ignore
            return

    return preexec


def run_code_in_subprocess(code: str, timeout_s: int = 2, *, cpu_seconds: Optional[int] = 2, mem_limit_mb: Optional[int] = 200) -> Tuple[int, str, str]:
    """Run `code` in the bundled `_subprocess_worker.py` and return outputs.

    Parameters:
      - code: source text to send to the worker via JSON on stdin.
      - timeout_s: wall-clock timeout for the whole operation (seconds).
      - cpu_seconds: optional RLIMIT_CPU (seconds) applied on POSIX.
      - mem_limit_mb: optional RLIMIT_AS (MB) applied on POSIX.

    Returns (returncode, stdout, stderr). On timeout the function will kill
    the process and return (-1, "", "TIMEOUT").
    """
    runner_path = Path(__file__).parent / "_subprocess_worker.py"
    if not runner_path.exists():
        raise FileNotFoundError(str(runner_path))

    # Keep the child's environment minimal to reduce accidental access to
    # host secrets. We still pass a minimal PATH so the python interpreter
    # can locate shared libraries if needed.
    env = {"PATH": os.environ.get("PATH", "")}

    popen_kwargs = dict(
        args=[sys.executable, str(runner_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        close_fds=True,
    )

    preexec = None
    if os.name != "nt":
        preexec = _make_posix_preexec(cpu_seconds, mem_limit_mb)
        popen_kwargs["preexec_fn"] = preexec
    else:
        # On Windows we can still create a new process group to help signal
        # handling; creationflags could be used for JobObject isolation but
        # that's outside the scope here.
        popen_kwargs["creationflags"] = 0

    proc = subprocess.Popen(**popen_kwargs)

    payload = json.dumps({"code": code})
    try:
        out, err = proc.communicate(payload, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        return -1, "", "TIMEOUT"

    return proc.returncode, out or "", err or ""
