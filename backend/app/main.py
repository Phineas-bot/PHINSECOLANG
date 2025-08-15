from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any
import time

from ..ecolang.interpreter import Interpreter
from .. import db

app = FastAPI(title="EcoLang API", version="0.1")
interpreter = Interpreter()


@app.on_event('startup')
def startup():
    db.init_db()

class RunRequest(BaseModel):
    code: str
    inputs: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None
    script_id: Optional[int] = None

@app.post("/run")
async def run_code(req: RunRequest):
    start = time.time()
    try:
        result = interpreter.run(req.code, inputs=req.inputs or {}, settings=req.settings or {})
    except Exception as e:
        return {"output": "", "warnings": [], "eco": None, "duration_ms": int((time.time()-start)*1000), "errors": {"code": "SERVER_ERROR", "message": str(e)}}
    result["duration_ms"] = int((time.time()-start)*1000)

    # persist successful runs
    try:
        if result.get('errors') is None and result.get('eco'):
            eco = result['eco']
            db.save_run(req.script_id, eco.get('energy_J'), eco.get('energy_kWh'), eco.get('co2_g'), eco.get('total_ops'), result.get('duration_ms'), eco.get('tips'))
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
