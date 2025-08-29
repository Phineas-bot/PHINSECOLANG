#!/usr/bin/env python3
"""
Universal Green Code Wrapper (portable)

Runs an arbitrary command, measures elapsed time, parses ECO_OPS from stdout,
and computes EcoLang-style energy and CO2 using the same default parameters
as the EcoLang interpreter.

Usage (PowerShell):
  D:/ECOLANG/PHINSECOLANG/.venv/Scripts/python.exe scripts/greenwrap.py \
    --cmd "D:/ECOLANG/PHINSECOLANG/.venv/Scripts/python.exe scripts/bench/bench.py" \
    --warmup 1 --runs 5

Contract: benchmark programs must print a line like `ECO_OPS: <integer>`
or a JSON fragment containing "eco_ops": <integer> on stdout.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


ECO_OPS_REGEX = re.compile(r"ECO_OPS:\s*(\d+)")
ECO_OPS_JSON_REGEX = re.compile(r'"eco_ops"\s*:\s*(\d+)')


@dataclass
class Params:
    energy_per_op_J: float = 1e-9
    idle_power_W: float = 0.5
    co2_per_kwh_g: float = 475


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Universal Green Code Wrapper")
    p.add_argument(
        "--cmd",
        required=True,
        help="Command to run. Pass as a single string. Quoting should consider your shell (PowerShell).",
    )
    p.add_argument("--cwd", type=str, default=None, help="Working directory for the command")
    p.add_argument("--warmup", type=int, default=1, help="Warm-up runs (ignored in stats)")
    p.add_argument("--runs", type=int, default=5, help="Measured runs (median reported)")
    p.add_argument("--timeout", type=float, default=None, help="Per-run timeout in seconds")
    p.add_argument("--energy-per-op-j", type=float, default=1e-9, help="Energy per op [J]")
    p.add_argument("--idle-power-w", type=float, default=0.5, help="Idle power [W]")
    p.add_argument("--co2-per-kwh-g", type=float, default=475, help="Grid intensity [g/kWh]")
    p.add_argument("--print-stdout", action="store_true", help="Echo child stdout to this process stdout")
    return p.parse_args()


def run_once(cmd: str, cwd: Optional[str], timeout: Optional[float], echo: bool) -> tuple[float, str, int]:
    t0 = time.perf_counter()
    try:
        # Use shell=True to keep it simple across Windows/PowerShell; trusted local usage.
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise SystemExit(f"Timeout after {timeout}s running: {cmd}")
    dt = time.perf_counter() - t0
    out = (proc.stdout or "") + (proc.stderr or "")
    if echo and out:
        sys.stdout.write(out)
        sys.stdout.flush()
    return dt, out, proc.returncode


def parse_ops(stdout: str) -> Optional[int]:
    m = ECO_OPS_REGEX.search(stdout)
    if m:
        return int(m.group(1))
    j = ECO_OPS_JSON_REGEX.search(stdout)
    if j:
        return int(j.group(1))
    return None


def compute_metrics(ops: int, elapsed_s: float, params: Params) -> dict:
    energy_J = params.idle_power_W * elapsed_s + params.energy_per_op_J * float(ops)
    co2_g = energy_J / 3_600_000.0 * params.co2_per_kwh_g
    return {
        "elapsed_s": elapsed_s,
        "ops": ops,
        "energy_J": energy_J,
        "co2_g": co2_g,
        "params": {
            "energy_per_op_J": params.energy_per_op_J,
            "idle_power_W": params.idle_power_W,
            "co2_per_kwh_g": params.co2_per_kwh_g,
        },
        "backend": "time_only+reported_ops",
    }


def median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    mid = len(s) // 2
    if len(s) % 2:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])


def main() -> None:
    ns = parse_args()
    params = Params(
        energy_per_op_J=ns.energy_per_op_j,
        idle_power_W=ns.idle_power_w,
        co2_per_kwh_g=ns.co2_per_kwh_g,
    )

    times: List[float] = []
    stdout_last = ""
    rc_last = 0

    total = max(0, ns.warmup) + max(1, ns.runs)
    for i in range(total):
        dt, out, rc = run_once(ns.cmd, ns.cwd, ns.timeout, ns.print_stdout)
        stdout_last = out
        rc_last = rc
        if i >= ns.warmup:
            times.append(dt)

    if rc_last != 0:
        sys.stderr.write(f"Child process exited with code {rc_last}\n")
        sys.stderr.flush()

    ops = parse_ops(stdout_last)
    if ops is None:
        raise SystemExit("Failed to parse ECO_OPS from child stdout. Ensure the program prints 'ECO_OPS: <int>' or JSON with 'eco_ops'.")

    elapsed_s = median(times)
    metrics = compute_metrics(ops, elapsed_s, params)

    result = {
        "cmd": ns.cmd,
        "cwd": ns.cwd or str(Path.cwd()),
        "warmup": ns.warmup,
        "runs": ns.runs,
        "times_s": times,
        "stdout_tail": stdout_last[-400:],
        **metrics,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
