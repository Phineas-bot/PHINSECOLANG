"""Compare EcoLang vs Python vs Node for the nested if/else snippet.

Writes scripts/bench/if_nested_results.csv with columns:
language,elapsed_s,ops,energy_J,co2_g
and appends a final comment line indicating the greenest (lowest energy_J).
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
VENV_PY = REPO / ".venv" / "Scripts" / "python.exe"
PY = VENV_PY if VENV_PY.exists() else Path(sys.executable)
WRAP = REPO / "scripts" / "greenwrap.py"
BENCH_DIR = Path(__file__).resolve().parent


def run_ecolang() -> Dict:
    # Inline EcoLang source equivalent to the provided snippet
    src = (
        'let a = 2\n'
        'if a > 0 then\n'
        '  if a == 2 then\n'
        '    say "inner-yes"\n'
        '  else\n'
        '    say "inner-no"\n'
        '  end\n'
        'else\n'
        '  say "outer-no"\n'
        'end\n'
    )
    t0 = time.perf_counter()
    from backend.ecolang.interpreter import Interpreter  # type: ignore

    it = Interpreter()
    res = it.run(src)
    elapsed_s = time.perf_counter() - t0
    eco = res.get("eco") or {}
    return {
        "language": "EcoLang",
        "elapsed_s": float(elapsed_s),
        "ops": int(eco.get("total_ops", 0)),
        "energy_J": float(eco.get("energy_J", 0.0)),
        "co2_g": float(eco.get("co2_g", 0.0)),
    }


def run_wrapper(cmd: str, name: str) -> Dict:
    # Use wrapper to get JSON metrics for external languages
    p = subprocess.run(
        [str(PY), str(WRAP), "--cmd", cmd, "--warmup", "0", "--runs", "5"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        shell=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"wrapper failed for {name}: {p.stderr}")
    obj = json.loads(p.stdout)
    return {
        "language": name,
        "elapsed_s": float(obj.get("elapsed_s", 0.0)),
        "ops": int(obj.get("ops", 0)),
        "energy_J": float(obj.get("energy_J", 0.0)),
        "co2_g": float(obj.get("co2_g", 0.0)),
    }


def main() -> None:
    rows: List[Dict] = []
    # EcoLang (internal interpreter)
    rows.append(run_ecolang())
    # Python equivalent
    py_cmd = f"{PY} {BENCH_DIR / 'if_nested.py'}"
    rows.append(run_wrapper(py_cmd, "Python"))
    # Node equivalent (if available)
    node_path = "node"
    node_cmd = f"{node_path} {BENCH_DIR / 'if_nested.js'}"
    try:
        rows.append(run_wrapper(node_cmd, "Node"))
    except Exception:
        pass

    # Determine greenest by lowest energy_J
    green = min(rows, key=lambda r: r["energy_J"]) if rows else None

    # Write CSV
    out_csv = BENCH_DIR / "if_nested_results.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["language", "elapsed_s", "ops", "energy_J", "co2_g"])
        for r in rows:
            w.writerow([r["language"], f"{r['elapsed_s']:.9f}", r["ops"], f"{r['energy_J']:.9f}", f"{r['co2_g']:.9f}"])
        if green:
            f.write(f"# Greener: {green['language']} (lowest energy_J)\n")

    print(str(out_csv))


if __name__ == "__main__":
    main()
