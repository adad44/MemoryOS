from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ML_ROOT = PROJECT_ROOT / "ml"
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from memoryos.db import connect

from .abstraction_engine import run_abstraction
from .ollama_client import MODEL, is_ollama_running


VALID_BELIEF_TYPES = {"interest", "knowledge", "gap", "pattern", "project"}
_abstraction_lock = threading.Lock()


def _loads_list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def latest_user_model() -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT summary, top_interests, active_projects, work_rhythm, knowledge_gaps, generated_at
            FROM user_model
            ORDER BY generated_at DESC
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return None
    return {
        "status": "ready",
        "summary": row["summary"],
        "top_interests": _loads_list(row["top_interests"]),
        "active_projects": _loads_list(row["active_projects"]),
        "work_rhythm": row["work_rhythm"] or "",
        "knowledge_gaps": _loads_list(row["knowledge_gaps"]),
        "generated_at": row["generated_at"],
    }


def list_beliefs(belief_type: Optional[str] = None, min_confidence: float = 0.0, limit: int = 50) -> list[dict]:
    if belief_type and belief_type not in VALID_BELIEF_TYPES:
        raise ValueError("belief_type must be one of: interest, knowledge, gap, pattern, project")
    where = ["confidence >= ?"]
    params: list[object] = [min_confidence]
    if belief_type:
        where.append("belief_type = ?")
        params.append(belief_type)
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT topic, belief_type, summary, confidence, depth, times_reinforced, last_updated
            FROM beliefs
            WHERE {' AND '.join(where)}
            ORDER BY confidence DESC, times_reinforced DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def delete_belief(topic: str) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM beliefs WHERE topic = ?", (topic,))
        conn.commit()
        return cursor.rowcount > 0


def abstraction_runs(limit: int = 10) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, started_at, finished_at, captures_read, beliefs_written, beliefs_updated, status, error
            FROM abstraction_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def abstraction_status() -> dict:
    return {
        "ollama_running": is_ollama_running(),
        "model": MODEL,
        "running": _abstraction_lock.locked(),
    }


def trigger_abstraction_background() -> bool:
    if _abstraction_lock.locked():
        return False

    def run() -> None:
        with _abstraction_lock:
            try:
                run_abstraction()
            except Exception:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return True
