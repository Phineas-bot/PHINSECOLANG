import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow overriding the DB file used by the application (useful for tests)
DB_PATH = Path(
    os.environ.get('ECOLANG_DB_PATH') or Path(__file__).parent / 'ecolang.db'
)


def get_conn():
    """Return a new sqlite3 connection configured to return rows as dict-like objects.

    We create a fresh connection per-call. For the small scale of this project
    this simple approach is fine; if the app required high concurrency we would
    switch to a connection pool or an async driver.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Ensure the database file and required tables exist.

    This is idempotent and safe to call at application startup. It creates
    simple tables for users, scripts and runs used by the API and tests.
    """
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


def save_script(
    title: str,
    code_text: str,
    user_id: Optional[int] = None,
    eco_stats: Optional[Dict[str, Any]] = None,
) -> int:
    """Persist a script and optionally an initial run's eco-stats.

    Returns the new script_id. If `eco_stats` is provided we persist a
    corresponding run row after creating the script.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO Scripts (user_id, title, code_text) VALUES (?, ?, ?)',
        (user_id, title, code_text),
    )
    script_id = cur.lastrowid
    conn.commit()
    conn.close()
    # optionally save a first run entry if eco_stats provided
    if eco_stats:
        save_run(
            script_id,
            eco_stats.get("energy_J"),
            eco_stats.get("energy_kWh"),
            eco_stats.get("co2_g"),
            eco_stats.get("total_ops"),
            eco_stats.get("duration_ms"),
            eco_stats.get("tips"),
        )
    return script_id


def list_scripts() -> List[Dict[str, Any]]:
    """Return a list of saved scripts (id, title, created_at) ordered by newest.

    The returned items are plain dictionaries suitable for JSON serialization.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        'SELECT script_id, title, created_at FROM Scripts '
        'ORDER BY created_at DESC'
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_script(script_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single script by id, returning None if not found."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        'SELECT script_id, title, code_text, created_at FROM Scripts '
        'WHERE script_id = ?',
        (script_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def save_run(
    script_id: Optional[int],
    energy_J: Optional[float],
    energy_kWh: Optional[float],
    co2_g: Optional[float],
    total_ops: Optional[int],
    duration_ms: Optional[int],
    tips: Optional[List[str]] = None,
) -> int:
    """Persist a run row and return its run_id.

    The `tips` argument (if provided) is JSON-serialized into the `tips` TEXT
    column. Callers should treat this operation as non-fatal for UX: if saving
    fails, the API should still return the interpreter result.
    """
    conn = get_conn()
    cur = conn.cursor()
    tips_json = json.dumps(tips or [])
    cur.execute(
        """
        INSERT INTO Runs (
            script_id, energy_J, energy_kWh, co2_g, total_ops,
            duration_ms, tips
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            script_id,
            energy_J,
            energy_kWh,
            co2_g,
            total_ops,
            duration_ms,
            tips_json,
        ),
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def list_runs(script_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """List run rows, optionally filtering by script_id.

    Each returned dict has parsed `tips` as a Python list.
    """
    conn = get_conn()
    cur = conn.cursor()
    if script_id:
        cur.execute(
            (
                "SELECT run_id, script_id, energy_kWh, co2_g, total_ops,"
                " duration_ms, tips, created_at FROM Runs WHERE script_id = ?"
                " ORDER BY created_at DESC"
            ),
            (script_id,),
        )
    else:
        cur.execute(
            (
                "SELECT run_id, script_id, energy_kWh, co2_g, total_ops,"
                " duration_ms, tips, created_at FROM Runs ORDER BY created_at DESC"
            )
        )
    rows = cur.fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d['tips'] = json.loads(d.get('tips') or '[]')
        except Exception:
            # tolerate corrupt JSON in the DB by returning an empty list
            d['tips'] = []
        out.append(d)
    return out
