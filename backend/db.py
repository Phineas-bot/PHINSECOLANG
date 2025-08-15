import sqlite3
import json
from typing import Optional, Dict, Any, List
from pathlib import Path

DB_PATH = Path(__file__).parent / 'ecolang.db'


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS Users (
      user_id INTEGER PRIMARY KEY,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS Scripts (
      script_id INTEGER PRIMARY KEY,
      user_id INTEGER NULL,
      title TEXT NOT NULL,
      code_text TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS Runs (
      run_id INTEGER PRIMARY KEY,
      script_id INTEGER NULL,
      energy_J REAL,
      energy_kWh REAL,
      co2_g REAL,
      total_ops INTEGER,
      duration_ms INTEGER,
      tips TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()


def save_script(title: str, code_text: str, user_id: Optional[int] = None, eco_stats: Optional[Dict[str, Any]] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT INTO Scripts (user_id, title, code_text) VALUES (?, ?, ?)', (user_id, title, code_text))
    script_id = cur.lastrowid
    conn.commit()
    conn.close()
    # optionally save a first run entry if eco_stats provided
    if eco_stats:
        save_run(script_id, eco_stats.get('energy_J'), eco_stats.get('energy_kWh'), eco_stats.get('co2_g'), eco_stats.get('total_ops'), eco_stats.get('duration_ms'), eco_stats.get('tips'))
    return script_id


def list_scripts() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT script_id, title, created_at FROM Scripts ORDER BY created_at DESC')
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_script(script_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT script_id, title, code_text, created_at FROM Scripts WHERE script_id = ?', (script_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def save_run(script_id: Optional[int], energy_J: Optional[float], energy_kWh: Optional[float], co2_g: Optional[float], total_ops: Optional[int], duration_ms: Optional[int], tips: Optional[List[str]] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    tips_json = json.dumps(tips or [])
    cur.execute('''INSERT INTO Runs (script_id, energy_J, energy_kWh, co2_g, total_ops, duration_ms, tips) VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (script_id, energy_J, energy_kWh, co2_g, total_ops, duration_ms, tips_json))
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def list_runs(script_id: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    if script_id:
        cur.execute('SELECT run_id, script_id, energy_kWh, co2_g, total_ops, duration_ms, tips, created_at FROM Runs WHERE script_id = ? ORDER BY created_at DESC', (script_id,))
    else:
        cur.execute('SELECT run_id, script_id, energy_kWh, co2_g, total_ops, duration_ms, tips, created_at FROM Runs ORDER BY created_at DESC')
    rows = cur.fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d['tips'] = json.loads(d.get('tips') or '[]')
        except Exception:
            d['tips'] = []
        out.append(d)
    return out
