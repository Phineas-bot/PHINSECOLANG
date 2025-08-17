"""FastAPI application entrypoints for EcoLang.

This module exposes HTTP endpoints used by the frontend and tests. It keeps
handlers intentionally small: each `/run` request constructs a fresh
`Interpreter` to avoid cross-request state sharing and calls the interpreter's
public API. Server-side caps are enforced to prevent clients from overriding
resource/safety limits.
"""

import time
from typing import Any, Dict, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from .. import db
from ..ecolang.interpreter import Interpreter

app = FastAPI(title="EcoLang API", version="0.1")


def _cap_settings(settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Enforce server-side safe caps for runtime tunables.

    Clients may include a `settings` object with per-run tunables. The server
    must not trust these entirely; `_cap_settings` establishes a conservative
    ceiling using a fresh `Interpreter()` defaults and then applies the
    client's requested values up to those ceilings.

    Returns a dict suitable for passing directly into `Interpreter.run`.
    """
    # create a fresh Interpreter to obtain server-side safe defaults
    defaults = Interpreter()
    safe = {
        "max_steps": defaults.max_steps,
        "max_loop": defaults.max_loop,
        "max_time_s": defaults.max_time_s,
        "max_output_chars": defaults.max_output_chars,
    }
    if not settings:
        return safe
    caps = {}
    # coerce and clamp numeric values to the server's safe maximums
    caps["max_steps"] = min(int(settings.get("max_steps", safe["max_steps"])), safe["max_steps"])
    caps["max_loop"] = min(int(settings.get("max_loop", safe["max_loop"])), safe["max_loop"])
    caps["max_time_s"] = min(float(settings.get("max_time_s", safe["max_time_s"])), safe["max_time_s"])
    caps["max_output_chars"] = min(int(settings.get("max_output_chars", safe["max_output_chars"])), safe["max_output_chars"])
    # include other eco-related settings which are read by the interpreter
    caps["energy_per_op_J"] = float(settings.get("energy_per_op_J", defaults.energy_per_op_J))
    caps["idle_power_W"] = float(settings.get("idle_power_W", defaults.idle_power_W))
    caps["co2_per_kwh_g"] = float(settings.get("co2_per_kwh_g", defaults.co2_per_kwh_g))
    return caps


@app.on_event('startup')
def startup():
    """FastAPI startup event: initialize the database connection/schema."""
    db.init_db()


class RunRequest(BaseModel):
    """Pydantic model for the `/run` request body.

    Fields:
        code: EcoLang source text (string with lines/commands).
        inputs: optional mapping for `ask` statements.
        settings: optional runtime tunables; will be capped server-side.
        script_id: optional id to associate this run with a saved script.
    """
    code: str
    inputs: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None
    script_id: Optional[int] = None


@app.post("/run")
async def run_code(req: RunRequest):
    """Handle a code execution request.

    This endpoint builds a fresh `Interpreter` instance per-request to ensure
    isolation. It enforces server-side caps, applies them to the instance, and
    calls `Interpreter.run`. On success it optionally persists eco stats to
    the database. Any exceptions are turned into a SERVER_ERROR response so
    callers receive a stable JSON shape.
    """
    start = time.time()
    try:
        # enforce server-side caps and create a fresh Interpreter for this request
        capped = _cap_settings(req.settings or {})
        it = Interpreter()
        # apply caps to this per-request interpreter instance
        it.max_steps = capped.get("max_steps", it.max_steps)
        it.max_loop = capped.get("max_loop", it.max_loop)
        it.max_time_s = capped.get("max_time_s", it.max_time_s)
        it.max_output_chars = capped.get("max_output_chars", it.max_output_chars)
        # run with the capped settings (eco tunables are read from settings by interpreter)
        result = it.run(
            req.code,
            inputs=req.inputs or {},
            settings=capped,
        )
    except Exception as e:
        # Return a consistent error payload instead of raising
        return {
            "output": "",
            "warnings": [],
            "eco": None,
            "duration_ms": int((time.time() - start) * 1000),
            "errors": {"code": "SERVER_ERROR", "message": str(e)},
        }
    result["duration_ms"] = int((time.time()-start)*1000)

    # persist successful runs (non-fatal; on failure we append a warning)
    try:
        if result.get('errors') is None and result.get('eco'):
            eco = result['eco']
            db.save_run(
                req.script_id,
                eco.get("energy_J"),
                eco.get("energy_kWh"),
                eco.get("co2_g"),
                eco.get("total_ops"),
                result.get("duration_ms"),
                eco.get("tips"),
            )
    except Exception as e:
        # non-fatal: include warning but don't fail the request
        result.setdefault('warnings', []).append(f"Failed to persist run: {e}")

    return result


class SaveScriptRequest(BaseModel):
    title: str
    code: str
    eco_stats: Optional[Dict[str, Any]] = None


@app.post('/save')
async def save_script(req: SaveScriptRequest):
    try:
        script_id = db.save_script(req.title, req.code, None, req.eco_stats)
    except Exception as e:
        return {'error': str(e)}
    return {'script_id': script_id}


@app.get('/scripts')
async def list_scripts():
    return db.list_scripts()


@app.get('/scripts/{script_id}')
async def get_script(script_id: int):
    s = db.get_script(script_id)
    if not s:
        return {'error': 'not found'}
    return s


@app.get('/stats')
async def list_stats(script_id: Optional[int] = None):
    return db.list_runs(script_id)
