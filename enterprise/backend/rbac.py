from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import Depends, HTTPException

from .auth import current_principal
from .schemas import Principal


ROLE_LEVEL = {"member": 1, "manager": 2, "admin": 3, "auditor": 3, "owner": 4}
ROLE_ALLOWED = {
    "member": {"member", "manager", "admin", "auditor", "owner"},
    "manager": {"manager", "admin", "owner"},
    "admin": {"admin", "owner"},
    "auditor": {"auditor", "admin", "owner"},
    "owner": {"owner"},
}


def require_role(min_role: str):
    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in ROLE_ALLOWED[min_role]:
            raise HTTPException(status_code=403, detail=f"Requires {min_role} role.")
        return principal

    return dependency


def can_read_project_memory(role: str) -> bool:
    return ROLE_LEVEL.get(role, 0) >= ROLE_LEVEL["member"]


def can_admin_policy(role: str) -> bool:
    return role in ROLE_ALLOWED["admin"]


def is_org_admin(role: str) -> bool:
    return role in ROLE_ALLOWED["admin"]


def ensure_user_in_org(conn: sqlite3.Connection, organization_id: int, user_id: int) -> None:
    user = conn.execute(
        "SELECT id FROM users WHERE id = ? AND organization_id = ? AND status = 'active'",
        (user_id, organization_id),
    ).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found in organization.")


def ensure_team_in_org(conn: sqlite3.Connection, organization_id: int, team_id: Optional[int]) -> None:
    if team_id is None:
        return
    team = conn.execute(
        "SELECT id FROM teams WHERE id = ? AND organization_id = ?",
        (team_id, organization_id),
    ).fetchone()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found in organization.")


def ensure_project_in_org(
    conn: sqlite3.Connection,
    organization_id: int,
    project_id: Optional[int],
    team_id: Optional[int] = None,
) -> None:
    if project_id is None:
        return
    query = """
        SELECT projects.id, projects.team_id
        FROM projects
        JOIN teams ON teams.id = projects.team_id
        WHERE projects.id = ? AND teams.organization_id = ?
    """
    project = conn.execute(query, (project_id, organization_id)).fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found in organization.")
    if team_id is not None and int(project["team_id"]) != team_id:
        raise HTTPException(status_code=422, detail="Project does not belong to the requested team.")


def require_team_access(conn: sqlite3.Connection, principal: Principal, team_id: Optional[int]) -> None:
    if team_id is None:
        return
    ensure_team_in_org(conn, principal.organization_id, team_id)
    if is_org_admin(principal.role):
        return
    membership = conn.execute(
        """
        SELECT id
        FROM team_memberships
        WHERE team_id = ? AND user_id = ?
        """,
        (team_id, principal.user_id),
    ).fetchone()
    if not membership:
        raise HTTPException(status_code=403, detail="User is not a member of this team.")


def require_project_access(conn: sqlite3.Connection, principal: Principal, project_id: Optional[int]) -> None:
    if project_id is None:
        return
    ensure_project_in_org(conn, principal.organization_id, project_id)
    if is_org_admin(principal.role):
        return
    membership = conn.execute(
        """
        SELECT project_memberships.id
        FROM project_memberships
        WHERE project_id = ? AND user_id = ?
        UNION
        SELECT team_memberships.id
        FROM team_memberships
        JOIN projects ON projects.team_id = team_memberships.team_id
        WHERE projects.id = ? AND team_memberships.user_id = ?
        """,
        (project_id, principal.user_id, project_id, principal.user_id),
    ).fetchone()
    if not membership:
        raise HTTPException(status_code=403, detail="User is not a member of this project.")


def require_device_access(conn: sqlite3.Connection, principal: Principal, device_id: int, *, require_trusted: bool = False) -> None:
    device = conn.execute(
        "SELECT * FROM devices WHERE id = ? AND organization_id = ?",
        (device_id, principal.organization_id),
    ).fetchone()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found in organization.")
    if not is_org_admin(principal.role) and int(device["user_id"]) != principal.user_id:
        raise HTTPException(status_code=403, detail="User cannot access this device.")
    if require_trusted and device["trust_state"] != "trusted":
        raise HTTPException(status_code=403, detail="Device is not trusted for team memory sync.")
