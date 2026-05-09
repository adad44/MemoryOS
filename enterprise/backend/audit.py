from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def log_event(
    conn: sqlite3.Connection,
    organization_id: Optional[int],
    actor_user_id: Optional[int],
    actor_type: str,
    action: str,
    resource_type: str,
    resource_id: Optional[Any] = None,
    details: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO audit_events
        (organization_id, actor_user_id, actor_type, action, resource_type, resource_id, ip_address, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id,
            actor_user_id,
            actor_type,
            action,
            resource_type,
            str(resource_id) if resource_id is not None else None,
            ip_address,
            json.dumps(details or {}, separators=(",", ":")),
            now(),
        ),
    )
    return int(cursor.lastrowid)


def parse_details(row: dict[str, Any]) -> dict[str, Any]:
    try:
        row["details"] = json.loads(row.get("details") or "{}")
    except Exception:
        row["details"] = {}
    return row

