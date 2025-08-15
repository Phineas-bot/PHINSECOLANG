# EcoLang – Full Software Specification Document

**Project Title:** EcoLang – An Eco‑Friendly Educational Programming Language
**Version:** 1.0
**Architecture Style:** 2‑Tier Client–Server (Frontend web app + Backend API with DB)
**Target Duration:** 4 weeks

---

## 1. Executive Summary

EcoLang is a lightweight, Python‑inspired programming language and interpreter that teaches coding fundamentals while promoting green computing practices. Users write EcoLang code in a web editor, run it on a backend interpreter, and receive output plus an estimated eco impact report (energy/CO₂). Scripts and run history are persisted in a small database. The system is deployed online and accessible from modern browsers.

**Why it’s different:** Eco awareness is built into the language: eco tips, energy estimates, performance hints, and friendly errors.

---

## 2. Goals & Non‑Goals

### 2.1 Goals

* Simple, beginner‑friendly syntax with \~10–15 keywords.
* Secure, sandboxed interpreter with clear, educational errors.
* Eco impact estimation on every run (energy + gCO₂) with optimization tips.
* Web editor + API + small database for persistence (scripts + run stats).
* Online deployment with basic CI/CD.

### 2.2 Non‑Goals

* Not a full general‑purpose language; no OOP or complex libraries.
* No plugin ecosystem or native file/network access from user scripts.
* Not a heavy multi‑service microservice system.

---

## 3. Stakeholders & Personas

* **Student/Beginners:** Learn coding basics + eco awareness.
* **Instructor/Assessor:** Runs demos, reviews saved scripts and stats.
* **Developer (you):** Builds/maintains frontend, API, interpreter, DB.

---

## 4. Scope

### 4.1 In Scope

* Web editor with Run/Save/Load.
* Backend interpreter (lexer, parser, AST, evaluator).
* Eco metrics (ops count, time, energy, gCO₂) + teaching tips.
* Authentication ( lightweight) for saving per user.
* Deployment to public internet.

### 4.2 Out of Scope


* Binary modules, network/file I/O from scripts.

---

## 5. System Overview

**2‑Tier Client–Server:**

* **Client:** Browser UI (HTML/CSS/JS or React). Sends code to API, displays output + metrics, manages saved scripts.
* **Server:** Python FastAPI app providing `/run`, `/save`, `/load`, `/scripts/{id}`, `/stats` endpoints. Contains the EcoLang interpreter, eco‑impact estimator, and DB layer (SQLite/PostgreSQL).

High‑level data flow:

```
Browser (Editor) → POST /run → Interpreter → Output + EcoStats → (persist) → DB
Browser (Save)  → POST /save → DB
Browser (Load)  → GET  /load → DB → Scripts + Stats
```

---

## 6. Detailed Requirements

### 6.1 Functional Requirements (FR)

* **FR1:** User can author EcoLang code in a browser editor.
* **FR2:** User can execute code; receives stdout, warnings, eco tips, and eco metrics.
* **FR3:** User can save a script with title and optional description.
* **FR4:** User can view list of saved scripts and open one.
* **FR5:** System stores each run’s eco stats linked to script.
* **FR6 :** Basic authentication (register/login) to scope scripts to user.

### 6.2 Non‑Functional Requirements (NFR)

* **Usability:** Minimal UI, clear buttons, readable fonts, mobile‑friendly.
* **Performance:** Median `/run` latency ≤ 2s for scripts ≤ 200 lines.
* **Capacity:** Support ≥ 10 concurrent users on free tier hosting.
* **Security:** Sandboxed interpreter; no filesystem/network from user code.
* **Availability:** ≥ 95% during demo week.
* **Observability:** Server logs structured; request IDs; basic error tracking.
* **Maintainability:** Clear modules; unit tests for lexer/parser/eval.

---

## 7. Language Specification (EcoLang)

### 7.1 Lexical Elements

* **Identifiers:** `[a-zA-Z_][a-zA-Z0-9_]*`
* **Numbers:** integers, decimals 
* **Strings:** `"..."`
* **Booleans:** `true`, `false`
* **Comments:** `#` to end of line
* **Whitespace:** spaces, tabs, newlines (ignored except inside strings)

### 7.2 Keywords (proposed)

`let, if, then, else, end, repeat, times, say, ask, warn, ecoTip, savePower`

### 7.3 Operators

`+  -  *  /  ==  !=  >  >=  <  <=  =` (assignment with `let` only)

### 7.4 Statements & Grammar (informal)

```
program        := statement*
statement      := say_stmt | assign_stmt | if_stmt | repeat_stmt | ask_stmt |
                  warn_stmt | eco_stmt | savepower_stmt
say_stmt       := 'say' expr
assign_stmt    := 'let' IDENT '=' expr
if_stmt        := 'if' expr 'then' statement* ('else' statement*)? 'end'
repeat_stmt    := 'repeat' NUMBER 'times' statement* 'end'
ask_stmt       := 'ask' IDENT
warn_stmt      := 'warn' expr
eco_stmt       := 'ecoTip'
savepower_stmt := 'savePower' NUMBER
expr           := literal | IDENT | binary_expr | string_concat
binary_expr    := expr ( '+' | '-' | '*' | '/' | '==' | '!=' | '>' | '<' | '>=' | '<=' ) expr
string_concat  := expr '+' expr (where one side resolves to string)
literal        := NUMBER | STRING | 'true' | 'false'
```

### 7.5 Semantics

* `say`: print value (coerces to string).
* `ask`: prompts client; in web MVP, simulated prompt via modal or input; backend receives value with execution request.
* `repeat`: executes inner block N times.
* `if … then … else … end`: standard conditional.
* `warn`: prints to a warnings stream; UI styles this distinctly.
* `ecoTip`: selects a random eco tip from list or DB table.
* `savePower n`: sets interpreter pacing and/or throttles heavy operations; contributes to tips.

---

## 8. Interpreter Design

### 8.1 Modules

* **Lexer/Tokenizer:** Regex‑based scanner → token stream.
* **Parser:** Recursive descent building AST nodes per grammar.
* **AST:** Node classes (Program, Say, Assign, If, Repeat, Ask, Warn, EcoTip, SavePower, BinOp, Literal, Identifier).
* **Evaluator/Runtime:** Walks AST, maintains environment (symbol table), performs I/O via pluggable hooks.
* **Sandbox:** Disallows file/network/system calls; timeouts & step limits; memory cap.
* **Eco Meter:** Operation counters (`print`, `loop_check`, `math`, `assign`, `io`), wall‑clock time; applies estimation formula to compute J, kWh, gCO₂; generates suggestions.

### 8.2 Execution Limits (safety)

* Max statements per run: configurable (e.g., 100k steps).
* Max loop iterations: configurable (e.g., 10k).
* Max execution time: e.g., 1.5s.
* Max output length: e.g., 5k chars.

### 8.3 Error Handling

* Syntax errors with caret location and hint (“expected `end`”).
* Runtime errors with friendly cause (“undefined variable `x`”).

---

## 9. Eco Impact Estimation

### 9.1 Metrics

* `total_ops` (weighted)
* `compute_energy_J = total_ops * energy_per_op_J`
* `runtime_overhead_J = exec_time_s * idle_power_W`
* `total_energy_kWh = (compute + overhead) / 3_600_000`
* `co2_g = total_energy_kWh * co2_per_kwh_g`

### 9.2 Tunables (defaults)

* `energy_per_op_J = 1e-9`
* `idle_power_W = 0.5`
* `co2_per_kwh_g = 475`
* `ops_map = { print:50, loop_check:5, math:10, assign:5, io:200, optimize:1000, other:5 }`

### 9.3 Output

* Summary card: Joules, kWh, gCO₂, green tip, and simple suggestion (e.g., “reduce loop count by 50%”).

---

## 10. API Specification (Backend)

### 10.1 Authentication (Optional MVP)

* **POST /auth/register** → `{username, password}` → `201 {userId}`
* **POST /auth/login** → `{username, password}` → `200 {token}` (JWT)
* All endpoints accept anonymous access in MVP if auth deferred.

### 10.2 Run Code

* **POST /run**
* **Body:**

```json
{
  "code": "say \"Hello\"\nrepeat 3 times\n    say \"Eco!\"\nend",
  "inputs": {"answer": "yes"},
  "settings": {"energy_per_op_J": 1e-9, "idle_power_W": 0.5}
}
```

* **Response 200:**

```json
{
  "output": "Hello\nEco!\nEco!\nEco!\n",
  "warnings": ["High energy usage detected"],
  "eco": {
    "total_ops": 5500,
    "energy_J": 0.0250055,
    "energy_kWh": 6.945972222222222e-09,
    "co2_g": 0.0000033,
    "tips": ["Reduce loop count to save energy"]
  },
  "duration_ms": 37,
  "errors": null
}
```

### 10.3 Save Script & Stats

* **POST /save**
* **Body:**

```json
{
  "title": "Eco demo",
  "code": "say \"Hi\"",
  "eco_stats": {"energy_kWh": 6.9e-9, "co2_g": 0.0000033, "total_ops": 5500}
}
```

* **Response:** `201 { "script_id": 123 }`

### 10.4 List Scripts

* **GET /scripts** → `200 [{script_id, title, created_at}]`

### 10.5 Get Script by Id

* **GET /scripts/{id}** → `200 {script_id, title, code_text, created_at}`

### 10.6 List Stats

* **GET /stats?script\_id=123** → `200 [{run_id, energy_kWh, co2_g, run_date}]`

### 10.7 Error Format

```json
{
  "error": {
    "code": "SYNTAX_ERROR",
    "message": "Expected 'end' to close repeat block",
    "line": 3,
    "column": 1
  }
}
```

---

## 11. Database Schema

**Option A (SQLite single file) for MVP**
**Option B (PostgreSQL) for deployment**

Tables:

```
Users (
  user_id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

Scripts (
  script_id INTEGER PRIMARY KEY,
  user_id INTEGER NULL REFERENCES Users(user_id),
  title TEXT NOT NULL,
  code_text TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

Runs (
  run_id INTEGER PRIMARY KEY,
  script_id INTEGER NULL REFERENCES Scripts(script_id),
  energy_J REAL,
  energy_kWh REAL,
  co2_g REAL,
  total_ops INTEGER,
  duration_ms INTEGER,
  tips TEXT, -- JSON string array
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Indexes:**

* `idx_scripts_user` on `Scripts(user_id)`
* `idx_runs_script` on `Runs(script_id)`

---

## 12. Security Model & Sandboxing

* No filesystem or network APIs exposed to user scripts.
* Execution timeouts and step limits; abort on exceed.
* Memory cap via AST evaluator safeguards.
* Input values passed explicitly; no environment access.
* Server endpoints protected with CORS and optional JWT auth.
* HTTPS only in production.

---

## 13. UI/UX Specification

* **Pages:** Editor, Saved Scripts, Run History (per script), About.
* **Editor View:**

  * Code textarea (monospace), line numbers optional.
  * Buttons: Run, Save, Load, Clear.
  * Output panel: stdout, warnings (styled), eco card (energy, CO₂, tip).
* **Saved Scripts:** Table/list with title, date, actions (open, delete\*).
* **Run History:** Simple list of previous runs with eco metrics.
* **Accessibility:** High‑contrast theme toggle, keyboard shortcuts.

---

## 14. Deployment & Environments

* **Frontend:** Static hosting (Netlify/Vercel/GitHub Pages).
* **Backend:** Render/Railway/Heroku (Python FastAPI + Gunicorn/Uvicorn).
* **DB:** SQLite file
