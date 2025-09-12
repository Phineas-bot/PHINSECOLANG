# EcoLang — Low-Level Design (LLD) UML Diagrams

This document provides UML-style diagrams (via Mermaid) for the EcoLang system.

## Use Case Diagram

```mermaid
flowchart LR
	actorUser((User))
	actorGuest((Guest))

	subgraph SystemBoundary[EcoLang System]
		UC_Login([Login / Register])
		UC_Edit([Edit Code])
		UC_Inputs([Provide Inputs])
		UC_Run([Run Program])
		UC_Save([Save Script])
		UC_Open([Open Script])
		UC_Stats([View Run History / Eco Stats])
		UC_Tutorial([Read Tutorial / Try Samples])
		UC_Logout([Logout])
	end

	actorGuest -- can --> UC_Tutorial
	actorUser -- performs --> UC_Login
	actorUser -- performs --> UC_Edit
	actorUser -- performs --> UC_Inputs
	actorUser -- performs --> UC_Run
	actorUser -- performs --> UC_Save
	actorUser -- performs --> UC_Open
	actorUser -- performs --> UC_Stats
	actorUser -- performs --> UC_Tutorial
	actorUser -- performs --> UC_Logout
```

## Class Diagram

```mermaid
classDiagram
	class App {
		+state: token, apiBase, theme
		+code: string
		+inputsText: string
		+runCode(): Promise
		+saveScript(): Promise
		+openScript(id): Promise
	}

	class Interpreter {
		+max_steps: int
		+max_loop: int
		+max_time_s: float
		+max_output_chars: int
		+run(code, inputs, settings) Dict
		-_dispatch_statement(...)
		-_handle_if(...)
		-_handle_repeat(...)
		-_handle_while(...)
		-_handle_for(...)
		-_execute_block_inline(...)
		-_compute_eco(total_ops, duration_s) Dict
	}

	class SafeEvaluator {
		+visit_*(astNode)
	}

	class FastAPIApp {
		+/auth/register
		+/auth/login
		+/run
		+/save
		+/scripts
		+/scripts/{id}
		+/stats
	}

	class DB {
		+init_db()
		+create_user(username, hash) int
		+get_user_by_username(username) Dict
		+save_script(title, code, user_id, eco?) int
		+get_script(id) Dict
		+list_scripts(user_id?) List
		+save_run(script_id, energy_J, energy_kWh, co2_g, total_ops, duration_ms, tips) int
		+list_runs(script_id?) List
	}

	class Models {
		<<Pydantic>>
		RunRequest
		SaveScriptRequest
		TokenOut
	}

	App --> FastAPIApp : fetch()
	FastAPIApp ..> Models
	FastAPIApp --> Interpreter : per-request run
	FastAPIApp --> DB : CRUD
	Interpreter --> SafeEvaluator : uses
```

## Sequence Diagrams (5)

### 1) User Registration/Login

```mermaid
sequenceDiagram
	participant U as User
	participant FE as Frontend (App)
	participant API as FastAPI
	participant DB as SQLite
	U->>FE: Enter username/password
	FE->>API: POST /auth/register or /auth/login
	API->>DB: get_user_by_username / create_user
	DB-->>API: user row / id
	API-->>FE: 200 + {access_token}
	FE->>FE: Store token (localStorage)
```

### 2) Run Code with Inputs

```mermaid
sequenceDiagram
	participant U as User
	participant FE as Frontend (App)
	participant API as FastAPI
	participant INT as Interpreter
	participant DB as SQLite
	U->>FE: Click Run
	FE->>API: POST /run {code, inputs}
	API->>API: _cap_settings()
	API->>INT: new Interpreter(); run(...)
	INT->>INT: parse/dispatch; evaluate; account ops
	INT-->>API: result {output, warnings, eco}
	API->>DB: save_run(script_id?, eco, duration_ms)
	DB-->>API: run_id
	API-->>FE: 200 {output, warnings, eco, duration_ms}
	FE->>FE: Render Output/Eco/Warnings
```

### 3) Save Script

```mermaid
sequenceDiagram
	participant U as User
	participant FE as Frontend (App)
	participant API as FastAPI
	participant DB as SQLite
	U->>FE: Click Save
	FE->>API: POST /save {title, code} (Bearer)
	API->>DB: save_script(title, code, user_id)
	DB-->>API: script_id
	API-->>FE: 201 {script_id}
	FE->>API: GET /scripts (Bearer)
	API->>DB: list_scripts(user_id)
	DB-->>API: scripts[]
	API-->>FE: scripts[]
```

### 4) Open Script and View Stats

```mermaid
sequenceDiagram
	participant FE as Frontend (App)
	participant API as FastAPI
	participant DB as SQLite
	FE->>API: GET /scripts/{id} (Bearer)
	API->>DB: get_script(id)
	DB-->>API: {title, code_text, user_id}
	API-->>FE: script
	FE->>API: GET /stats?script_id=id (Bearer)
	API->>DB: list_runs(script_id)
	DB-->>API: runs[]
	API-->>FE: runs[]
	FE->>FE: Show code and history table
```

### 5) Interpreter While-Loop Execution (internal)

```mermaid
sequenceDiagram
	participant INT as Interpreter
	participant E as SafeEvaluator
	INT->>E: eval(condition)
	E-->>INT: true/false
	alt condition true
		INT->>INT: _execute_block_inline(block)
		INT->>INT: increment ops, loop checks
		INT->>E: eval(condition)
		E-->>INT: ...
	else condition false
		INT-->>INT: exit loop
	end
	INT-->>INT: return ops/out/warnings
```

## Activity Diagrams (3)

### A) Login Flow

```mermaid
flowchart TD
	A[Start] --> B[Enter credentials]
	B --> C{Mode?}
	C -- Register --> D[POST /auth/register]
	C -- Login --> E[POST /auth/login]
	D --> F{Success?}
	E --> F
	F -- Yes --> G[Store token]
	F -- No --> H[Show error]
	G --> I[Go to Editor]
	H --> B
	I --> J[End]
```

### B) Run Execution Flow

```mermaid
flowchart TD
	A[Start] --> B[User clicks Run]
	B --> C[POST /run]
	C --> D[Cap settings]
	D --> E[Interpreter.run]
	E --> F{Errors?}
	F -- Yes --> G[Return errors]
	F -- No --> H[Persist run stats]
	H --> I[Return output,warnings,eco]
	G --> I
	I --> J[End]
```

### C) Inputs Editor Sync (JSON ↔ Form)

```mermaid
flowchart TD
	A[Start] --> B{Mode switch?}
	B -- To Form --> C[Parse JSON -> rows]
	B -- To JSON --> D[Serialize rows -> JSON]
	C --> E{JSON valid?}
	E -- No --> F[Show notice; start empty/default]
	E -- Yes --> G[Hydrate rows]
	D --> H[Update textarea]
	F --> I[User edits rows]
	G --> I
	I --> D
	H --> J[End]
```

## Deployment Diagram

```mermaid
flowchart LR
	subgraph Client
		B[Web Browser]
	end
	subgraph FrontendHost
		V[Vite Dev Server / Static Host]
	end
	subgraph BackendHost
		U[Uvicorn + FastAPI]
		DB[(SQLite File)]
	end

	B <--HTTP--> V
	V <--HTTP JSON--> U
	U <--SQL--> DB
```

