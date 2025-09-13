# EcoLang – Final Report

## Technology Stack

### Programming languages

- Python (backend, interpreter, tests)
- JavaScript (React/Vite frontend)
- Markdown (documentation)
- PowerShell (helper scripts on Windows)

### Frameworks and libraries

- Backend
  - FastAPI 0.109.x (web API)
  - Starlette 0.36.x (ASGI under FastAPI)
  - Pydantic 1.10.x (request/response models)
  - Uvicorn 0.22.x (ASGI server)
  - PyJWT 2.8.x (JWT auth)
  - bcrypt 4.1.x (password hashing)
  - SQLite (built-in) via simple helpers in `backend/db.py`
- Interpreter (core)
  - Custom AST-based, sandboxed evaluator in `backend/ecolang/interpreter.py`
- Frontend
  - React 18 + Vite (SPA)
  - Basic CSS (no heavy UI framework)

### Tools and services

- Netlify (frontend deploy; `netlify.toml`)
- Railway (backend deploy target; `Procfile` + `nixpacks.toml`)
- Cloudflare Tunnel (local backend → public HTTPS for the live frontend)
- GitHub Actions (CI workflows)
- Git (GitHub repository)

### Dev/build/deploy configuration

- `Procfile` (Uvicorn start command): `web: python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- `nixpacks.toml` (Railway): installs `backend/requirements.txt`, starts Uvicorn app
- `netlify.toml` (frontend): base=`frontend`, publish=`dist`, SPA redirects, `VITE_API_BASE` env wiring
- Helper scripts (Windows):
  - `scripts/start-local-backend-and-tunnel.ps1`
  - `scripts/stop-local-backend-and-tunnel.ps1`

### Testing and CI

- Pytest-based tests in `backend/tests/`
- GitHub Actions workflows: CI and stress suites

## Results and Discussion

### What was built

- A working EcoLang playground with:
  - React/Vite SPA: Editor (code + Inputs JSON/Form), Saved Scripts, About (interactive tutorial), and Landing (auth)
  - FastAPI backend: `/auth/*`, `/run`, `/save`, `/scripts`, `/stats`
  - Safe interpreter: variables, expressions, conditionals, loops (repeat/while/for), functions, arrays, inputs; strict limits
  - Eco metrics per run: total operations, energy (J/kWh), CO₂ (g), and tips

### Deployments achieved

- Frontend deployed on Netlify, configured to call the backend via a Cloudflare Tunnel (public HTTPS) that exposes the local backend during development.
- Backend runs locally (Uvicorn) and is prepared for Railway deployment with `Procfile` + `nixpacks.toml`.

### Documentation and UX

- Architecture docs: `archi.md` (HLD), diagrams, design notes
- Tutorial: aligned examples strictly to the interpreter rules (e.g., `while … then … end`, `repeat N` with integer literal, one top‑level `elif`) so all samples run unmodified
- Practical tips surfaced via `ecoTip` and warning messages; FAQ clarifies capabilities and limits

### Architecture discussion

- Client–server SPA with stateless REST endpoints provides a clean separation of concerns and portability
- In-process interpreter keeps latency low and simplifies accounting, while strict caps and whitelisting reduce risk
- SQLite is sufficient for current dev/load; persistence enables auth-scoped scripts and run history without extra services

## Conclusion and Future Work

### Summary of the project outcomes

- A functional, safe, and approachable coding environment that also teaches resource-aware programming
- A live frontend (Netlify) and ready-to-deploy backend (Railway) using simple, reproducible configs
- A set of runnable tutorial examples that map exactly to supported language features

### Challenges and solutions

- Netlify `netlify.toml` parse error → removed duplicate blocks and validated syntax
- Railway “No start command” → added `Procfile` and `nixpacks.toml` to declare install/start steps
- Port conflicts (8000 busy) → switched local backend to `127.0.0.1:8001` when needed
- Inputs type mismatch (string vs number) → use `toNumber(age)` before numeric comparison
- Tutorial conformance issues (multiple `elif`, `repeat` with variable, missing `then`) → rewrote examples to the exact grammar
- Dependency compatibility (FastAPI/Pydantic) → pinned FastAPI 0.109.x and Pydantic 1.10.x
- Tunnel setup on Windows → added PowerShell helpers and used Cloudflare Tunnel binary for stable PATH

### Technical challenges faced

- Safe code execution: keeping the language expressive while constraining the AST and runtime
- Preventing runaway resource usage: step/time/output/loop caps and bounded recursion
- Cross-deployment ergonomics: monorepo detection for platform builds (Nixpacks), SPA routing, and environment variables across hosts
- Documentation correctness: ensuring every tutorial snippet is actually runnable against the current interpreter

### How these challenges were overcome

- Implemented a whitelisted AST evaluator and per-run budgets (steps, time, output), plus function depth/params caps
- Added explicit platform configs (`Procfile`, `nixpacks.toml`, `netlify.toml`) and helper scripts to standardize local run and tunnel
- Audited and refactored all tutorial examples; enforced fences, language hints, and no inline comments in runnable code
- Pinned backend dependency versions to a known-good set to avoid framework-breaking changes

### Lessons learned

- Small, clear language contracts (e.g., `while` requires `then`, literal-only `repeat`) make docs and runtime predictable
- Surfaces for type coercion (`toNumber`, `toString`) are essential when reading external inputs
- Treat deployment config as code (Procfile/Nixpacks/Netlify) to avoid platform-specific surprises
- Developer experience wins matter: helper scripts and linted docs reduce friction

### Suggestions for future improvements and features

- Backend
  - Deploy to Railway (stable HTTPS URL), tighten CORS, add rate limiting and structured logging
  - Move from SQLite to Postgres with pooling for higher concurrency; add migrations
  - Offload heavy/long runs to worker processes or a job queue for isolation
- Language/interpreter
  - Add `break/continue`, more safe helpers (e.g., min/max, sum, slice), and simple profiling hooks
  - Consider controlled array mutation helpers (still sandboxed)
- Frontend
  - Allow switching API base at runtime (avoid rebuilds); wire `VITE_API_BASE` from platform UI env vars
  - Add shareable permalinks (code + inputs + results), dark mode refinements, and guided exercises
- Quality & Ops
  - Expand tests (property-based tests for interpreter), add coverage, and introduce minimal e2e tests
  - Harden secrets/HTTPS in production; add observability and guardrails in CI

---

EcoLang demonstrates that a friendly beginner experience and awareness of eco impact can coexist. The current architecture is intentionally simple yet robust enough to teach fundamentals safely—while leaving clear upgrade paths for scale, features, and production hardening.


