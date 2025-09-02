"""Compare EcoLang vs Python vs Node for the nested if/else snippet across N.

Writes scripts/bench/if_nested_results.csv with columns:
N,language,elapsed_s,ops,energy_J,co2_g
and appends a final comment line indicating the overall greenest by median energy.
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
        "elapsed_s": float(elapsed_s),
        "ops": int(eco.get("total_ops", 0)),
        "energy_J": float(eco.get("energy_J", 0.0)),
        "co2_g": float(eco.get("co2_g", 0.0)),
    }


def run_wrapper(cmd: str) -> Dict:
    # Use wrapper to get JSON metrics for external languages
    p = subprocess.run(
        [str(PY), str(WRAP), "--cmd", cmd, "--warmup", "0", "--runs", "5"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        shell=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"wrapper failed: {p.stderr}")
    obj = json.loads(p.stdout)
    return {
        "elapsed_s": float(obj.get("elapsed_s", 0.0)),
        "ops": int(obj.get("ops", 0)),
        "energy_J": float(obj.get("energy_J", 0.0)),
        "co2_g": float(obj.get("co2_g", 0.0)),
    }


def main() -> None:
    rows: List[Dict] = []
    Ns = [10000, 100000, 500000]
    for N in Ns:
        os.environ["ECO_BENCH_N"] = str(N)
        # EcoLang (internal interpreter) — run once per N (its ops are estimated)
        eco = run_ecolang()
        rows.append({"N": N, "language": "EcoLang", **eco})
        # Python
        py_cmd = f"{PY} {BENCH_DIR / 'if_nested.py'}"
        py = run_wrapper(py_cmd)
        rows.append({"N": N, "language": "Python", **py})
        # Node if available
        try:
            node_cmd = f"node {BENCH_DIR / 'if_nested.js'}"
            nd = run_wrapper(node_cmd)
            rows.append({"N": N, "language": "Node", **nd})
        except Exception:
            pass

    # Determine overall greenest by median energy across Ns
    by_lang: Dict[str, List[float]] = {}
    for r in rows:
        by_lang.setdefault(r["language"], []).append(r["energy_J"])
    med = lambda xs: sorted(xs)[len(xs)//2]
    green_lang = min(by_lang.keys(), key=lambda k: med(by_lang[k])) if by_lang else None

    # Write CSV
    out_csv = BENCH_DIR / "if_nested_results.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["N", "language", "elapsed_s", "ops", "energy_J", "co2_g"])
        for r in rows:
            w.writerow([r["N"], r["language"], f"{r['elapsed_s']:.9f}", r["ops"], f"{r['energy_J']:.9f}", f"{r['co2_g']:.9f}"])
        if green_lang:
            f.write(f"# Greener (median energy across N): {green_lang}\n")

    print(str(out_csv))


if __name__ == "__main__":
    main()
