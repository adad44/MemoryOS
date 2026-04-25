from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ML_ROOT = PROJECT_ROOT / "ml"
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from memoryos.db import connect

try:
    from .ollama_client import extract_json, generate
    from .prompts import (
        BELIEF_EXTRACTION_SYSTEM,
        USER_MODEL_SYSTEM,
        build_extraction_prompt,
        build_user_model_prompt,
    )
except ImportError:
    from ollama_client import extract_json, generate
    from prompts import (
        BELIEF_EXTRACTION_SYSTEM,
        USER_MODEL_SYSTEM,
        build_extraction_prompt,
        build_user_model_prompt,
    )


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("abstraction_engine")

VALID_BELIEF_TYPES = {"interest", "knowledge", "gap", "pattern", "project"}
VALID_DEPTHS = {"surface", "familiar", "intermediate", "deep"}


def get_recent_captures(hours: int = 6) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, app_name, window_title, content, timestamp, source_type
            FROM captures
            WHERE (is_noise = 0 OR is_noise IS NULL)
              AND timestamp >= ?
              AND length(content) > 50
            ORDER BY timestamp DESC
            LIMIT 60
            """,
            (since,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_existing_beliefs(limit: int = 30) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT topic, belief_type, summary, confidence, depth, times_reinforced
            FROM beliefs
            ORDER BY confidence DESC, times_reinforced DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def write_new_belief(belief: dict, capture_ids: list[int]) -> bool:
    required = ["topic", "belief_type", "summary", "confidence"]
    if not all(key in belief for key in required):
        log.warning("Belief missing required fields: %s", belief)
        return False

    topic = str(belief["topic"]).strip()
    belief_type = str(belief["belief_type"]).strip()
    summary = str(belief["summary"]).strip()
    if not topic or not summary or belief_type not in VALID_BELIEF_TYPES:
        log.warning("Invalid belief payload: %s", belief)
        return False

    depth = belief.get("depth") or "surface"
    if depth not in VALID_DEPTHS:
        depth = "surface"
    confidence = max(0.0, min(1.0, float(belief.get("confidence", 0.5))))

    with connect() as conn:
        existing = conn.execute("SELECT id FROM beliefs WHERE LOWER(topic) = LOWER(?)", (topic,)).fetchone()
        if existing:
            log.info("Belief already exists for topic: %s", topic)
            return False
        conn.execute(
            """
            INSERT INTO beliefs (topic, belief_type, summary, confidence, depth, evidence)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                topic[:200],
                belief_type,
                summary[:500],
                confidence,
                depth,
                json.dumps(capture_ids[:10]),
            ),
        )
        conn.commit()
    return True


def reinforce_belief(topic: str) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            """
            UPDATE beliefs
            SET times_reinforced = times_reinforced + 1,
                confidence = MIN(confidence + 0.05, 0.95),
                last_updated = CURRENT_TIMESTAMP
            WHERE LOWER(topic) = LOWER(?)
            """,
            (topic,),
        )
        conn.commit()
        return cursor.rowcount > 0


def generate_user_model() -> bool:
    beliefs = get_existing_beliefs(limit=80)
    if not beliefs:
        log.info("No beliefs yet - skipping user model generation")
        return False

    prompt = build_user_model_prompt(beliefs)
    log.info("Generating user model summary")
    response = generate(prompt, system=USER_MODEL_SYSTEM)
    if not response:
        log.error("Empty response from Ollama for user model")
        return False

    parsed = extract_json(response)
    if not parsed:
        log.error("Failed to parse user model JSON: %s", response[:200])
        return False

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO user_model (summary, top_interests, active_projects, work_rhythm, knowledge_gaps, raw_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(parsed.get("summary", ""))[:1000],
                json.dumps(parsed.get("top_interests", [])),
                json.dumps(parsed.get("active_projects", [])),
                str(parsed.get("work_rhythm", ""))[:500],
                json.dumps(parsed.get("knowledge_gaps", [])),
                json.dumps(parsed),
            ),
        )
        conn.commit()
    return True


def _start_run() -> int:
    with connect() as conn:
        cursor = conn.execute("INSERT INTO abstraction_runs (status) VALUES ('running')")
        conn.commit()
        return int(cursor.lastrowid)


def _finish_run(run_id: int, captures_read: int, beliefs_written: int, beliefs_updated: int) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE abstraction_runs
            SET status = 'complete',
                finished_at = CURRENT_TIMESTAMP,
                captures_read = ?,
                beliefs_written = ?,
                beliefs_updated = ?
            WHERE id = ?
            """,
            (captures_read, beliefs_written, beliefs_updated, run_id),
        )
        conn.commit()


def _fail_run(run_id: int, error: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE abstraction_runs
            SET status = 'failed',
                finished_at = CURRENT_TIMESTAMP,
                error = ?
            WHERE id = ?
            """,
            (error[:1000], run_id),
        )
        conn.commit()


def run_abstraction(hours: int = 6) -> dict:
    run_id = _start_run()
    captures_read = 0
    beliefs_written = 0
    beliefs_updated = 0

    try:
        captures = get_recent_captures(hours=hours)
        captures_read = len(captures)
        log.info("Read %s recent captures", captures_read)

        if captures_read < 5:
            _finish_run(run_id, captures_read, beliefs_written, beliefs_updated)
            return {
                "run_id": run_id,
                "status": "complete",
                "captures_read": captures_read,
                "beliefs_written": beliefs_written,
                "beliefs_updated": beliefs_updated,
            }

        existing_beliefs = get_existing_beliefs()
        prompt = build_extraction_prompt(captures, existing_beliefs)
        log.info("Calling Ollama for belief extraction")
        response = generate(prompt, system=BELIEF_EXTRACTION_SYSTEM)
        if not response:
            raise RuntimeError("Empty response from Ollama")

        parsed = extract_json(response)
        if not parsed:
            raise RuntimeError(f"Failed to parse JSON from response: {response[:300]}")

        capture_ids = [int(capture["id"]) for capture in captures]
        for belief in parsed.get("new_beliefs", []):
            if write_new_belief(belief, capture_ids):
                beliefs_written += 1

        for topic in parsed.get("reinforced_topics", []):
            if reinforce_belief(str(topic)):
                beliefs_updated += 1

        for gap in parsed.get("gaps_detected", []):
            gap_belief = {
                "topic": str(gap),
                "belief_type": "gap",
                "summary": f"User engages with '{gap}' but shows limited deep retention",
                "confidence": 0.55,
                "depth": "surface",
            }
            if write_new_belief(gap_belief, capture_ids):
                beliefs_written += 1

        generate_user_model()
        _finish_run(run_id, captures_read, beliefs_written, beliefs_updated)
        return {
            "run_id": run_id,
            "status": "complete",
            "captures_read": captures_read,
            "beliefs_written": beliefs_written,
            "beliefs_updated": beliefs_updated,
        }
    except Exception as exc:
        log.error("Abstraction run failed: %s", exc)
        _fail_run(run_id, str(exc))
        raise


if __name__ == "__main__":
    print(run_abstraction())
