# SQLite persistence for plan graphs.
import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from classes.logger import log


def _db_path():
    from classes import info
    base = getattr(info, "USER_PATH", os.path.expanduser("~/.openshot_qt"))
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "plan_history.db")


def _init_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS edit_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT NOT NULL,
            graph_json TEXT NOT NULL,
            breakdown_json TEXT,
            created_at REAL NOT NULL
        )
    """)
    conn.commit()


def save_plan(plan_builder):
    try:
        plan = plan_builder.get_plan_json()
        if not plan:
            return None
        path = _db_path()
        conn = sqlite3.connect(path)
        _init_schema(conn)
        prompt = plan.get("description") or plan.get("prompt") or ""
        graph_json = json.dumps(plan, default=str)
        breakdown = plan_builder.get_breakdown()
        breakdown_json = json.dumps(breakdown, default=str)
        created_at = time.time()
        cur = conn.execute(
            "INSERT INTO edit_plans (prompt, graph_json, breakdown_json, created_at) VALUES (?, ?, ?, ?)",
            (prompt, graph_json, breakdown_json, created_at),
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        log.debug("Plan saved: id=%s", row_id)
        return row_id
    except Exception as e:
        log.warning("Failed to save plan: %s", e)
        return None


def load_plan(plan_id):
    try:
        path = _db_path()
        if not os.path.isfile(path):
            return None
        conn = sqlite3.connect(path)
        row = conn.execute(
            "SELECT prompt, graph_json, breakdown_json, created_at FROM edit_plans WHERE id = ?",
            (plan_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": plan_id,
            "prompt": row[0],
            "graph": json.loads(row[1]) if row[1] else None,
            "breakdown": json.loads(row[2]) if row[2] else {},
            "created_at": row[3],
        }
    except Exception as e:
        log.warning("Failed to load plan %s: %s", plan_id, e)
        return None


def list_plans(limit=50):
    try:
        path = _db_path()
        if not os.path.isfile(path):
            return []
        conn = sqlite3.connect(path)
        _init_schema(conn)
        rows = conn.execute(
            "SELECT id, prompt, created_at FROM edit_plans ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [{"id": r[0], "prompt": (r[1] or "")[:200], "created_at": r[2]} for r in rows]
    except Exception as e:
        log.warning("Failed to list plans: %s", e)
        return []
