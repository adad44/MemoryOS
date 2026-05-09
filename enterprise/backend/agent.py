from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from .audit import log_event, now
from .auth import bearer_token, hash_secret
from .db import connect
from .policies import active_policy
from .rbac import ensure_project_in_org, ensure_team_in_org
from .schemas import AgentContextRequest, AgentContextResponse
from .sync import list_shared


def issue_agent_context(request: AgentContextRequest, authorization: Optional[str]) -> AgentContextResponse:
    token_hash = hash_secret(bearer_token(authorization))
    with connect() as conn:
        grant = conn.execute(
            "SELECT * FROM agent_access_grants WHERE token_hash = ? AND status = 'active'",
            (token_hash,),
        ).fetchone()
        if not grant:
            raise HTTPException(status_code=403, detail="Invalid or inactive agent grant.")
        if not bool(grant["can_read_shared"]):
            raise HTTPException(status_code=403, detail="Agent grant cannot read shared memory.")
        conn.execute("UPDATE agent_access_grants SET last_used_at = ? WHERE id = ?", (now(), grant["id"]))

        grant_team_id = int(grant["team_id"]) if grant["team_id"] is not None else None
        grant_project_id = int(grant["project_id"]) if grant["project_id"] is not None else None
        if grant_team_id is not None and request.team_id not in {None, grant_team_id}:
            raise HTTPException(status_code=403, detail="Agent grant is not scoped to the requested team.")
        if grant_project_id is not None and request.project_id not in {None, grant_project_id}:
            raise HTTPException(status_code=403, detail="Agent grant is not scoped to the requested project.")

        team_id = request.team_id if request.team_id is not None else grant_team_id
        project_id = request.project_id if request.project_id is not None else grant_project_id
        ensure_team_in_org(conn, int(grant["organization_id"]), team_id)
        ensure_project_in_org(conn, int(grant["organization_id"]), project_id, team_id)
        if team_id is None and project_id is None:
            raise HTTPException(status_code=403, detail="Agent grant requires a team or project scope.")
        shared = list_shared(conn, int(grant["organization_id"]), team_id, project_id, request.query, request.limit)
        policy = active_policy(conn, int(grant["organization_id"]))
        if request.include_private_recent:
            raise HTTPException(status_code=403, detail="Enterprise agent grants cannot read private local memory.")
        audit_id = log_event(
            conn,
            int(grant["organization_id"]),
            None,
            "agent",
            "agent_context_read",
            "agent_context",
            grant["id"],
            {
                "agent_name": grant["agent_name"],
                "shared_count": len(shared),
                "team_id": team_id,
                "project_id": project_id,
                "query_present": bool(request.query),
                "include_private_recent": request.include_private_recent,
            },
        )
        conn.commit()
        return AgentContextResponse(
            agent_name=str(grant["agent_name"]),
            shared_memories=shared,
            private_recent=[],
            policy_version=policy.version,
            audit_event_id=audit_id,
        )
