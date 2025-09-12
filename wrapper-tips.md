# Universal Green Code Wrapper — tips

This guide shows how to compare EcoLang-style energy/CO₂ across languages with a tiny, portable wrapper. It works on Windows PowerShell and requires no changes to your core project.

## What it does

- Runs any program you choose and measures elapsed time.
- Parses the program’s reported work units (ops) from stdout.
- Computes EcoLang-style estimates with the same defaults used by the interpreter:
  - energy_J = idle_power_W × elapsed_s + energy_per_op_J × ops
  - co2_g = energy_J / 3_600_000 × co2_per_kwh_g
  - Defaults: energy_per_op_J = 1e-9, idle_power_W = 0.5, co2_per_kwh_g = 475

Contract for programs

- Print either a line: `ECO_OPS: <integer>`
- Or include JSON containing: `"eco_ops": <integer>`

Examples are provided under `scripts/bench/` for Python, Node, Java, C, and C++.

## Files added

- `scripts/greenwrap.py`: Universal wrapper CLI (portable, time-only + reported ops)
- `scripts/bench/bench.py`: Python sample (prints ECO_OPS)
- `scripts/bench/bench.js`: Node.js sample
- `scripts/bench/Bench.java`: Java sample
- `scripts/bench/bench.c`: C sample
- `scripts/bench/bench.cpp`: C++ sample
- `scripts/bench/run-all.ps1`: PowerShell orchestrator that compiles/runs what’s available and prints a comparison table

## Quick start (PowerShell)

Run a single program through the wrapper:

```powershell
# Example: Python sample
D:/ECOLANG/PHINSECOLANG/.venv/Scripts/python.exe scripts/greenwrap.py --cmd "D:/ECOLANG/PHINSECOLANG/.venv/Scripts/python.exe scripts/bench/bench.py" --warmup 1 --runs 5
```

Run all available languages and compare (compiles where needed):

```powershell
# N = problem size, Warmup ignored in stats, Runs median reported
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bench/run-all.ps1 -N 1000000 -Warmup 1 -Runs 3
```

The wrapper produces JSON with `elapsed_s`, `ops`, `energy_J`, `co2_g`. The runner prints a small table (sorted by `elapsed_s`).

Environment knobs

- Set workload size via env var `ECO_BENCH_N` or with `-N` in `run-all.ps1`.
- Tweak energy parameters (if desired) in the wrapper:
  - `--energy-per-op-j`, `--idle-power-w`, `--co2-per-kwh-g`

## Tiny compile/run hints (Windows)

Node.js

```powershell
node scripts/bench/bench.js
```

Java

```powershell
# From repo root
javac scripts/bench/Bench.java
java -cp scripts/bench Bench
```

C (MSVC cl or MinGW/LLVM)

```powershell
# cl (Visual Studio Developer Command Prompt)
cl /O2 /Fe:scripts/bench/bench_c.exe scripts/bench/bench.c
scripts/bench/bench_c.exe

# gcc (MinGW) or clang
gcc -O3 -o scripts/bench/bench_c.exe scripts/bench/bench.c
# or
clang -O3 -o scripts/bench/bench_c.exe scripts/bench/bench.c
scripts/bench/bench_c.exe
```

C++ (MSVC cl or g++/clang++)

```powershell
# cl
cl /O2 /Fe:scripts/bench/bench_cpp.exe scripts/bench/bench.cpp
scripts/bench/bench_cpp.exe

# g++ or clang++
g++ -O3 -o scripts/bench/bench_cpp.exe scripts/bench/bench.cpp
# or
clang++ -O3 -o scripts/bench/bench_cpp.exe scripts/bench/bench.cpp
scripts/bench/bench_cpp.exe
```

Python

```powershell
D:/ECOLANG/PHINSECOLANG/.venv/Scripts/python.exe scripts/bench/bench.py
```

## Writing your own benchmark

- Use the same algorithm and same `N` across languages.
- Print `ECO_OPS: <N>` once the work completes.
- Keep systems quiet and repeat runs; ignore the first run (JIT/warm-up); compare medians.

## Troubleshooting

- “Program did not print ECO_OPS”: ensure the exact line `ECO_OPS: <integer>` appears on stdout.
- “Command not found”: provide a full path (e.g., to `java`, `node`, or `.exe`) or add to PATH.
- Java non-zero exit (e.g., 3221226505): verify JDK install and that `javac`/`java` match bitness; re-run from repo root.
- C/C++ compile errors: ensure you’re in a Developer Command Prompt (MSVC) or have MinGW/LLVM installed.

## What’s measured and what’s not

- Backend: `time_only+reported_ops` — cross-platform and simple.
- The energy/CO₂ values are estimates, not direct hardware energy. For higher fidelity later, you can integrate hardware tools (e.g., Intel Power Gadget on Windows, RAPL on Linux), but the time+ops approach is sufficient for consistent, apples-to-apples comparisons.

---

If you want, we can add a CSV/Markdown report generator that runs multiple `N` values and summarizes speed/energy per language.
