from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Optional

from fastapi import HTTPException

from .audit import log_event, now, row_dict
from .policies import active_policy, json_text, redact, redact_value, render_local_privacy_settings, render_local_storage_policy
from .rbac import ensure_project_in_org, require_device_access, require_project_access, require_team_access
from .schemas import Principal, ShareMemoryRequest, SharedMemory


def shared_memory_from_row(row: sqlite3.Row) -> SharedMemory:
    data = row_dict(row)
    try:
        metadata = json.loads(data.get("metadata") or "{}")
    except Exception:
        metadata = {}
    return SharedMemory(
        id=int(data["id"]),
        local_capture_id=data["local_capture_id"],
        team_id=data["team_id"],
        project_id=data["project_id"],
        shared_by_user_id=int(data["shared_by_user_id"]),
        policy_version=int(data["policy_version"]),
        share_state=str(data["share_state"]),
        title=data["title"],
        summary=str(data["summary"]),
        redacted_content=str(data["redacted_content"]),
        metadata=metadata,
        created_at=str(data["created_at"]),
    )


def policy_for_device(conn: sqlite3.Connection, principal: Principal, device_id: Optional[int]) -> dict[str, Any]:
    policy = active_policy(conn, principal.organization_id)
    if device_id is not None:
        require_device_access(conn, principal, device_id)
        conn.execute("UPDATE devices SET policy_version = ?, last_seen_at = ? WHERE id = ? AND organization_id = ?", (policy.version, now(), device_id, principal.organization_id))
        log_event(conn, principal.organization_id, principal.user_id, "user", "policy_synced", "device", device_id, {"policy_version": policy.version})
        conn.commit()
    return {
        "policy": policy.dict(),
        "privacy_settings": render_local_privacy_settings(policy),
        "storage_policy": render_local_storage_policy(policy),
    }


def share_local_capture(conn: sqlite3.Connection, principal: Principal, request: ShareMemoryRequest) -> SharedMemory:
    policy = active_policy(conn, principal.organization_id)
    if not policy.sync_enabled:
        raise HTTPException(status_code=409, detail="Team memory sync is disabled by enterprise policy.")
    require_team_access(conn, principal, request.team_id)
    ensure_project_in_org(conn, principal.organization_id, request.project_id, request.team_id)
    require_project_access(conn, principal, request.project_id)
    require_device_access(conn, principal, request.device_id, require_trusted=True)

    content = request.content
    redacted_content = redact(content, policy)
    summary = redact(request.summary or redacted_content[:500], policy)
    title = redact(request.title or request.window_title or request.url or f"Capture {request.local_capture_id}", policy)
    metadata = redact_value(
        {
            **request.metadata,
            "app_name": request.app_name,
            "window_title": request.window_title,
            "source_type": request.source_type,
            "url": request.url,
            "file_path": request.file_path,
            "device_id": request.device_id,
        },
        policy,
    )
    source_hash = hashlib.sha256(f"{request.local_capture_id}:{content}".encode("utf-8")).hexdigest()
    cursor = conn.execute(
        """
        INSERT INTO shared_memories
        (organization_id, local_capture_id, team_id, project_id, shared_by_user_id, policy_version,
         source_hash, title, summary, redacted_content, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            principal.organization_id,
            request.local_capture_id,
            request.team_id,
            request.project_id,
            principal.user_id,
            policy.version,
            source_hash,
            title,
            summary,
            redacted_content,
            json_text(metadata),
        ),
    )
    shared_id = int(cursor.lastrowid)
    conn.execute(
        """
        INSERT INTO memory_sync_events (organization_id, shared_memory_id, device_id, event_type, status, details)
        VALUES (?, ?, ?, 'share', 'complete', ?)
        """,
        (principal.organization_id, shared_id, request.device_id, json_text({"local_capture_id": request.local_capture_id})),
    )
    log_event(
        conn,
        principal.organization_id,
        principal.user_id,
        "user",
        "memory_shared",
        "shared_memory",
        shared_id,
        {
            "local_capture_id": request.local_capture_id,
            "device_id": request.device_id,
            "team_id": request.team_id,
            "project_id": request.project_id,
            "policy_version": policy.version,
            "redaction_terms": len(policy.redaction_terms),
        },
    )
    conn.commit()
    return shared_memory_from_row(conn.execute("SELECT * FROM shared_memories WHERE id = ?", (shared_id,)).fetchone())


def list_shared(
    conn: sqlite3.Connection,
    organization_id: int,
    team_id: Optional[int],
    project_id: Optional[int],
    query: Optional[str],
    limit: int,
    principal: Optional[Principal] = None,
) -> list[SharedMemory]:
    where = ["organization_id = ?", "share_state = 'shared'"]
    params: list[Any] = [organization_id]
    if principal is not None and principal.role not in {"admin", "auditor", "owner"}:
        where.append(
            """
            (
              team_id IN (SELECT team_id FROM team_memberships WHERE user_id = ?)
              OR project_id IN (SELECT project_id FROM project_memberships WHERE user_id = ?)
              OR project_id IN (
                SELECT projects.id
                FROM projects
                JOIN team_memberships ON team_memberships.team_id = projects.team_id
                WHERE team_memberships.user_id = ?
              )
              OR shared_by_user_id = ?
            )
            """
        )
        params.extend([principal.user_id, principal.user_id, principal.user_id, principal.user_id])
    if team_id is not None:
        where.append("team_id = ?")
        params.append(team_id)
    if project_id is not None:
        where.append("project_id = ?")
        params.append(project_id)
    if query:
        where.append("(LOWER(summary) LIKE ? OR LOWER(redacted_content) LIKE ?)")
        needle = f"%{query.lower()}%"
        params.extend([needle, needle])
    rows = conn.execute(
        f"SELECT * FROM shared_memories WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ?",
        [*params, limit],
    ).fetchall()
    return [shared_memory_from_row(row) for row in rows]
