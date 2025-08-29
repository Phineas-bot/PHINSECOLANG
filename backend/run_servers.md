# EcoLang Backend — API Quickstart & Language Features

This guide helps you run the backend locally, call the API, and understand what parts of the EcoLang language are implemented.

## Run the API locally (Windows PowerShell)

```powershell
# From repo root
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

# Start FastAPI with Uvicorn (default port 8000)
python -m uvicorn backend.app.main:app --reload --port 8000 --host 127.0.0.1
```

Open the interactive docs at: http://127.0.0.1:8000/docs

Notes

- CORS is permissive during development (allow_origins=["*"]). For production, restrict it.
- The DB is a local SQLite file at `backend/ecolang.db` by default.

## Try it: POST /run

Minimal “Hello” run:

```powershell
$body = @{ code = 'say "Hello Eco"' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/run -ContentType 'application/json' -Body $body
```

Example with inputs and settings caps:

```powershell
$payload = @{
	code = @'
let a = 1
if a == 1 then
	say "yes"
else
	say "no"
end
repeat 3 times
	warn "looping"
	say "loop"
end
ecoTip
'@
	inputs = @{ }
	settings = @{ max_time_s = 1.5; max_steps = 100000 }
	script_id = $null
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/run -ContentType 'application/json' -Body $payload
```

## Implemented endpoints

- POST `/run` — Execute EcoLang code. Returns `{output, warnings, eco, duration_ms, errors}` and persists run stats when successful.
- POST `/save` — Save a script: `{title, code, eco_stats?}` → `{script_id}`.
- GET `/scripts` — List scripts: `[{script_id, title, created_at}]`.
- GET `/scripts/{id}` — Get one script: `{script_id, title, code_text, created_at}`.
- GET `/stats?script_id=<id>` — List run stats (optionally filtered).

Auth endpoints are not implemented in the current build (optional per spec).

## Language features implemented

Statements

- `say <expr>` → prints stringified value.
- `let <name> = <expr>` → assigns to the environment.
- `warn <expr>` → adds a warning (stringified) to the result.
- `ask <name>` → reads a value from request `inputs` into the environment.
- `if <expr> then … [else …] end` → conditional with nested blocks.
- `repeat N times … end` → loops with per-iteration isolation; enforces max.
- `ecoTip` → outputs a simple tip line as normal output.
- `savePower N` → scales down operation costs (affects eco accounting) and adds a warning like `savePower applied: level N`.

Expressions (safe AST)

- Literals: numbers, strings, booleans (`true`/`false`).
- Variables: identifiers loaded from env.
- Operators: `+ - * /`, comparisons `== != < <= > >=`, unary `+`/`-`.
- String concat: `+` works when types permit (Python semantics).
- Disallowed: function calls, attributes, imports, subscripts, lambdas/comprehensions, function/class defs, `global`/`nonlocal`, dangerous names (`__import__`, `eval`, `exec`, `open`, `os`, `sys`).

Runtime limits & errors (server caps enforced)

- Defaults: `max_steps=100000`, `max_loop=10000`, `max_time_s=1.5`, `max_output_chars=5000`.
- Error codes returned in `errors`: `SYNTAX_ERROR`, `RUNTIME_ERROR`, `TIMEOUT`, `STEP_LIMIT` (also adds a human-readable warning), `OUTPUT_LIMIT`, `INTERNAL`.

Eco metrics

- Op accounting via `ops_map` (print/loop_check/math/assign/io/other).
- Energy model: `energy_J = total_ops*energy_per_op_J + runtime_overhead (time*idle_power_W)`; also returns `energy_kWh`, `co2_g`, and `tips` (adds one when `total_ops > 1000`).
- `savePower` lowers op costs going forward (affects eco numbers, not timing).

Optional subprocess mode

- If you pass `{"use_subprocess": true}` in settings, code is run by a tiny AST-whitelisted Python worker (not the EcoLang interpreter). This is mainly for tests/sandbox experiments.

## Example: save and list

```powershell
$save = @{ title = 'Eco demo'; code = 'say "Hi"' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/save -ContentType 'application/json' -Body $save

Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/scripts
```

## Troubleshooting

- If requests hang: verify Uvicorn is running at the expected host/port and that your shell isn’t blocking requests via a proxy.
- If DB errors appear: delete `backend/ecolang.db` to reset, or set `ECOLANG_DB_PATH` to a writable location.
- For frontend dev, point the UI to the backend base URL (CORS is open in dev).

