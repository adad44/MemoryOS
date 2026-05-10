from __future__ import annotations

import csv
import io
import json
from typing import Any, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .agent import issue_agent_context
from .audit import log_event, now, parse_details, row_dict
from .auth import hash_secret, require_bootstrap_token
from .config import load_settings
from .db import connect
from .policies import active_policy, publish_policy
from .rbac import ensure_project_in_org, ensure_team_in_org, ensure_user_in_org, is_org_admin, require_project_access, require_role, require_team_access
from .scim import router as scim_router
from .schemas import (
    AgentContextRequest,
    AgentContextResponse,
    AgentGrantRequest,
    AuditExport,
    BootstrapRequest,
    BootstrapResponse,
    DeviceRequest,
    EnterprisePolicy,
    MembershipRequest,
    OverviewResponse,
    Principal,
    ProjectRequest,
    ShareMemoryRequest,
    SharedMemory,
    TeamRequest,
    UserRequest,
)
from .sync import list_shared, policy_for_device, share_local_capture


app = FastAPI(
    title="MemoryOS Teams Enterprise Backend",
    version="0.1.0",
    description="Separate enterprise API for SSO, RBAC, policy sync, team memory sync, audit export, and Hermes Agent access.",
)
settings = load_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(scim_router)


@app.get("/admin/console", response_class=HTMLResponse)
def admin_console() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MemoryOS Teams Admin</title>
  <style>
    body { margin: 0; background: #f6f8fa; color: #0d141c; font-family: Inter, system-ui, sans-serif; }
    main { max-width: 1180px; margin: 0 auto; padding: 32px 20px; }
    header { display: flex; gap: 16px; align-items: center; justify-content: space-between; margin-bottom: 24px; }
    h1 { margin: 0; font-size: 32px; }
    input, textarea { width: 100%; border: 1px solid #cbd5df; border-radius: 8px; padding: 10px; font: inherit; }
    button { border: 0; border-radius: 8px; background: #111827; color: white; padding: 10px 14px; font-weight: 800; cursor: pointer; }
    section { background: white; border: 1px solid #dce3ea; border-radius: 8px; padding: 18px; margin: 14px 0; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
    .stat { border: 1px solid #e5eaf0; border-radius: 8px; padding: 12px; }
    .stat b { display: block; font-size: 28px; }
    pre { overflow: auto; background: #0d141c; color: #d7fbe8; border-radius: 8px; padding: 12px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid #edf1f5; padding: 8px; text-align: left; }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>MemoryOS Teams Admin</h1>
      <p>Enterprise control plane for policy, users, teams, devices, agents, audit, SCIM, and encryption status.</p>
    </div>
    <button onclick="loadAll()">Refresh</button>
  </header>
  <section>
    <label>Admin bearer token</label>
    <input id="token" type="password" placeholder="Paste SSO/JWT bearer token" />
  </section>
  <div class="grid" id="stats"></div>
  <section><h2>Policy</h2><textarea id="policy" rows="9"></textarea><p><button onclick="savePolicy()">Publish policy</button></p></section>
  <section><h2>Users</h2><div id="users"></div></section>
  <section><h2>Teams</h2><div id="teams"></div></section>
  <section><h2>Devices</h2><div id="devices"></div></section>
  <section><h2>Audit Export</h2><button onclick="exportAudit()">Download JSONL</button></section>
  <section><h2>SCIM</h2><pre id="scim"></pre></section>
</main>
<script>
const tokenInput = document.getElementById('token');
tokenInput.value = localStorage.memoryosEnterpriseToken || '';
tokenInput.addEventListener('input', () => localStorage.memoryosEnterpriseToken = tokenInput.value);
async function api(path, options = {}) {
  const res = await fetch(path, { ...options, headers: { 'Authorization': 'Bearer ' + tokenInput.value, 'Content-Type': 'application/json', ...(options.headers || {}) } });
  if (!res.ok) throw new Error(await res.text());
  return res.headers.get('content-type')?.includes('json') ? res.json() : res.text();
}
function table(rows, cols) {
  return '<table><thead><tr>' + cols.map(c => `<th>${c}</th>`).join('') + '</tr></thead><tbody>' +
    rows.map(r => '<tr>' + cols.map(c => `<td>${r[c] ?? ''}</td>`).join('') + '</tr>').join('') + '</tbody></table>';
}
async function loadAll() {
  const overview = await api('/admin/overview');
  document.getElementById('stats').innerHTML = [
    ['Users', overview.users.length], ['Teams', overview.teams.length], ['Projects', overview.projects.length],
    ['Devices', overview.devices.length], ['Shared memories', overview.shared_memory_count], ['Audit events', overview.audit_event_count]
  ].map(([k,v]) => `<div class="stat">${k}<b>${v}</b></div>`).join('');
  document.getElementById('policy').value = JSON.stringify(overview.policy, null, 2);
  document.getElementById('users').innerHTML = table(overview.users, ['id','email','name','role','status','last_seen_at']);
  document.getElementById('teams').innerHTML = table(overview.teams, ['id','name','description','created_at']);
  document.getElementById('devices').innerHTML = table(overview.devices, ['id','device_name','trust_state','policy_version','last_seen_at']);
  document.getElementById('scim').textContent = JSON.stringify(await api('/admin/scim/status'), null, 2);
}
async function savePolicy() { await api('/admin/policy', { method: 'PUT', body: document.getElementById('policy').value }); await loadAll(); }
async function exportAudit() {
  const text = await api('/audit/export?format=jsonl');
  const blob = new Blob([text], { type: 'application/x-ndjson' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'memoryos-audit.jsonl'; a.click();
}
</script>
</body>
</html>
"""


@app.get("/health")
def health() -> dict[str, Any]:
    settings = load_settings()
    return {
        "ok": True,
        "enterprise_enabled": settings.enabled,
        "sso_configured": bool((settings.oidc_jwks_url or settings.jwt_hs256_secret) and settings.oidc_audience),
        "database_engine": settings.database_engine,
        "database_configured": bool(settings.database_url),
        "encryption_enabled": settings.encryption_enabled,
        "kms_provider": settings.kms_provider,
        "scim_configured": bool(settings.scim_token),
    }


@app.post("/bootstrap", response_model=BootstrapResponse, dependencies=[Depends(require_bootstrap_token)])
def bootstrap(request: BootstrapRequest) -> BootstrapResponse:
    with connect() as conn:
        existing = conn.execute("SELECT * FROM organizations WHERE slug = ?", (request.organization_slug,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Organization already exists.")
        cursor = conn.execute(
            "INSERT INTO organizations (name, slug, sso_issuer, sso_audience) VALUES (?, ?, ?, ?)",
            (request.organization_name, request.organization_slug, request.sso_issuer, request.sso_audience),
        )
        org_id = int(cursor.lastrowid)
        user_cursor = conn.execute(
            """
            INSERT INTO users (organization_id, subject, email, name, role, last_seen_at)
            VALUES (?, ?, ?, ?, 'owner', ?)
            """,
            (org_id, request.owner_subject, request.owner_email, request.owner_name, now()),
        )
        owner_id = int(user_cursor.lastrowid)
        policy = active_policy(conn, org_id)
        log_event(conn, org_id, owner_id, "user", "enterprise_bootstrap", "organization", org_id)
        conn.commit()
        return BootstrapResponse(organization_id=org_id, owner_user_id=owner_id, policy=policy)


@app.get("/auth/me", response_model=Principal)
def me(principal: Principal = Depends(require_role("member"))) -> Principal:
    return principal


@app.get("/admin/overview", response_model=OverviewResponse)
def overview(principal: Principal = Depends(require_role("manager"))) -> OverviewResponse:
    with connect() as conn:
        org = conn.execute("SELECT * FROM organizations WHERE id = ?", (principal.organization_id,)).fetchone()
        users = [row_dict(row) for row in conn.execute("SELECT id, email, name, role, status, last_seen_at, created_at FROM users WHERE organization_id = ? ORDER BY name", (principal.organization_id,))]
        devices = [row_dict(row) for row in conn.execute("SELECT * FROM devices WHERE organization_id = ? ORDER BY registered_at DESC", (principal.organization_id,))]
        teams = [row_dict(row) for row in conn.execute("SELECT * FROM teams WHERE organization_id = ? ORDER BY name", (principal.organization_id,))]
        projects = [
            row_dict(row)
            for row in conn.execute(
                """
                SELECT projects.*
                FROM projects
                JOIN teams ON teams.id = projects.team_id
                WHERE teams.organization_id = ?
                ORDER BY projects.name
                """,
                (principal.organization_id,),
            )
        ]
        shared_count = int(conn.execute("SELECT COUNT(*) AS count FROM shared_memories WHERE organization_id = ?", (principal.organization_id,)).fetchone()["count"])
        audit_count = int(conn.execute("SELECT COUNT(*) AS count FROM audit_events WHERE organization_id = ?", (principal.organization_id,)).fetchone()["count"])
        return OverviewResponse(
            principal=principal,
            organization=row_dict(org),
            policy=active_policy(conn, principal.organization_id),
            users=users,
            devices=devices,
            teams=teams,
            projects=projects,
            shared_memory_count=shared_count,
            audit_event_count=audit_count,
        )


@app.get("/admin/scim/status")
def scim_status(principal: Principal = Depends(require_role("admin"))) -> dict[str, Any]:
    settings = load_settings()
    with connect() as conn:
        recent = [
            parse_details(row_dict(row))
            for row in conn.execute(
                """
                SELECT *
                FROM audit_events
                WHERE organization_id = ? AND actor_type = 'scim'
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (principal.organization_id,),
            )
        ]
    return {
        "configured": bool(settings.scim_token),
        "org_slug": settings.scim_org_slug,
        "recent_events": recent,
    }


@app.get("/admin/policy", response_model=EnterprisePolicy)
def get_policy(principal: Principal = Depends(require_role("member"))) -> EnterprisePolicy:
    with connect() as conn:
        return active_policy(conn, principal.organization_id)


@app.put("/admin/policy", response_model=EnterprisePolicy)
def put_policy(request: EnterprisePolicy, principal: Principal = Depends(require_role("admin"))) -> EnterprisePolicy:
    with connect() as conn:
        policy = publish_policy(conn, principal.organization_id, request, principal.user_id)
        log_event(conn, principal.organization_id, principal.user_id, "user", "policy_published", "policy", policy.version)
        conn.commit()
        return policy


@app.post("/admin/users")
def provision_user(request: UserRequest, principal: Principal = Depends(require_role("admin"))) -> dict[str, Any]:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (organization_id, subject, email, name, role, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(organization_id, subject)
            DO UPDATE SET email = excluded.email, name = excluded.name, role = excluded.role, status = excluded.status
            """,
            (principal.organization_id, request.subject, request.email, request.name, request.role, request.status),
        )
        user = conn.execute(
            "SELECT id, email, name, role, status, last_seen_at, created_at FROM users WHERE organization_id = ? AND subject = ?",
            (principal.organization_id, request.subject),
        ).fetchone()
        log_event(
            conn,
            principal.organization_id,
            principal.user_id,
            "user",
            "user_provisioned",
            "user",
            user["id"] if user else cursor.lastrowid,
            {"subject": request.subject, "role": request.role, "status": request.status},
        )
        conn.commit()
        return row_dict(user)


@app.post("/admin/teams")
def create_team(request: TeamRequest, principal: Principal = Depends(require_role("manager"))) -> dict[str, Any]:
    with connect() as conn:
        cursor = conn.execute("INSERT INTO teams (organization_id, name, description) VALUES (?, ?, ?)", (principal.organization_id, request.name, request.description))
        team_id = int(cursor.lastrowid)
        conn.execute("INSERT INTO team_memberships (team_id, user_id, role) VALUES (?, ?, 'owner')", (team_id, principal.user_id))
        log_event(conn, principal.organization_id, principal.user_id, "user", "team_created", "team", team_id)
        conn.commit()
        return row_dict(conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone())


@app.post("/admin/teams/{team_id}/members")
def add_team_member(team_id: int, request: MembershipRequest, principal: Principal = Depends(require_role("manager"))) -> dict[str, Any]:
    with connect() as conn:
        team = conn.execute("SELECT * FROM teams WHERE id = ? AND organization_id = ?", (team_id, principal.organization_id)).fetchone()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found.")
        ensure_user_in_org(conn, principal.organization_id, request.user_id)
        conn.execute("INSERT OR REPLACE INTO team_memberships (team_id, user_id, role) VALUES (?, ?, ?)", (team_id, request.user_id, request.role))
        log_event(conn, principal.organization_id, principal.user_id, "user", "team_member_upserted", "team", team_id, {"user_id": request.user_id, "role": request.role})
        conn.commit()
        return {"team_id": team_id, "user_id": request.user_id, "role": request.role}


@app.post("/admin/projects")
def create_project(request: ProjectRequest, principal: Principal = Depends(require_role("manager"))) -> dict[str, Any]:
    with connect() as conn:
        team = conn.execute("SELECT * FROM teams WHERE id = ? AND organization_id = ?", (request.team_id, principal.organization_id)).fetchone()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found.")
        cursor = conn.execute("INSERT INTO projects (team_id, name, description) VALUES (?, ?, ?)", (request.team_id, request.name, request.description))
        project_id = int(cursor.lastrowid)
        conn.execute("INSERT INTO project_memberships (project_id, user_id, role) VALUES (?, ?, 'owner')", (project_id, principal.user_id))
        log_event(conn, principal.organization_id, principal.user_id, "user", "project_created", "project", project_id)
        conn.commit()
        return row_dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())


@app.post("/sync/devices")
def register_device(request: DeviceRequest, principal: Principal = Depends(require_role("member"))) -> dict[str, Any]:
    with connect() as conn:
        public_key_hash = hash_secret(request.public_key) if request.public_key else None
        trust_state = request.trust_state if is_org_admin(principal.role) else "pending"
        cursor = conn.execute(
            """
            INSERT INTO devices (organization_id, user_id, device_name, trust_state, public_key_hash, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (principal.organization_id, principal.user_id, request.device_name, trust_state, public_key_hash, now()),
        )
        device_id = int(cursor.lastrowid)
        log_event(conn, principal.organization_id, principal.user_id, "user", "device_registered", "device", device_id, {"trust_state": trust_state})
        conn.commit()
        return row_dict(conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone())


@app.get("/sync/policy")
def sync_policy(device_id: Optional[int] = None, principal: Principal = Depends(require_role("member"))) -> dict[str, Any]:
    with connect() as conn:
        return policy_for_device(conn, principal, device_id)


@app.post("/sync/share", response_model=SharedMemory)
def share_memory(request: ShareMemoryRequest, principal: Principal = Depends(require_role("member"))) -> SharedMemory:
    with connect() as conn:
        return share_local_capture(conn, principal, request)


@app.get("/sync/shared", response_model=list[SharedMemory])
def shared_memory(
    team_id: Optional[int] = None,
    project_id: Optional[int] = None,
    query: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_role("member")),
) -> list[SharedMemory]:
    with connect() as conn:
        require_team_access(conn, principal, team_id)
        ensure_project_in_org(conn, principal.organization_id, project_id, team_id)
        require_project_access(conn, principal, project_id)
        items = list_shared(conn, principal.organization_id, team_id, project_id, query, limit, principal=principal)
        log_event(conn, principal.organization_id, principal.user_id, "user", "shared_memory_read", "shared_memory", None, {"count": len(items)})
        conn.commit()
        return items


@app.post("/admin/agent-grants")
def create_agent_grant(request: AgentGrantRequest, principal: Principal = Depends(require_role("admin"))) -> dict[str, Any]:
    with connect() as conn:
        if request.can_request_private:
            raise HTTPException(status_code=422, detail="Enterprise agent grants cannot read private local memory.")
        ensure_team_in_org(conn, principal.organization_id, request.team_id)
        ensure_project_in_org(conn, principal.organization_id, request.project_id, request.team_id)
        cursor = conn.execute(
            """
            INSERT INTO agent_access_grants
            (organization_id, agent_name, token_hash, team_id, project_id, can_request_private, created_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (principal.organization_id, request.agent_name, hash_secret(request.token), request.team_id, request.project_id, 1 if request.can_request_private else 0, principal.user_id),
        )
        grant_id = int(cursor.lastrowid)
        log_event(conn, principal.organization_id, principal.user_id, "user", "agent_grant_created", "agent_grant", grant_id, {"agent_name": request.agent_name})
        conn.commit()
        return {"id": grant_id, "agent_name": request.agent_name, "team_id": request.team_id, "project_id": request.project_id, "can_request_private": request.can_request_private}


@app.post("/agent/context", response_model=AgentContextResponse)
def hermes_agent_context(request: AgentContextRequest, authorization: Optional[str] = Header(default=None)) -> AgentContextResponse:
    return issue_agent_context(request, authorization)


@app.get("/audit/events", response_model=AuditExport)
def audit_events(limit: int = Query(default=500, ge=1, le=5000), principal: Principal = Depends(require_role("auditor"))) -> AuditExport:
    with connect() as conn:
        rows = [
            parse_details(row_dict(row))
            for row in conn.execute("SELECT * FROM audit_events WHERE organization_id = ? ORDER BY created_at DESC LIMIT ?", (principal.organization_id, limit))
        ]
        log_event(conn, principal.organization_id, principal.user_id, "user", "audit_events_read", "audit_event", None, {"count": len(rows)})
        conn.commit()
        return AuditExport(exported_at=now(), count=len(rows), events=rows)


@app.get("/audit/export")
def audit_export(
    format: Literal["jsonl", "csv"] = "jsonl",
    limit: int = Query(default=5000, ge=1, le=10000),
    principal: Principal = Depends(require_role("auditor")),
) -> Response:
    with connect() as conn:
        log_event(conn, principal.organization_id, principal.user_id, "user", "audit_exported", "audit_event", None, {"format": format, "limit": limit})
        conn.commit()
        rows = [
            parse_details(row_dict(row))
            for row in conn.execute("SELECT * FROM audit_events WHERE organization_id = ? ORDER BY created_at DESC LIMIT ?", (principal.organization_id, limit))
        ]
    if format == "jsonl":
        content = "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + ("\n" if rows else "")
        return Response(content=content, media_type="application/x-ndjson")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "organization_id", "actor_user_id", "actor_type", "action", "resource_type", "resource_id", "ip_address", "details", "created_at"])
    writer.writeheader()
    for row in rows:
        item = dict(row)
        item["details"] = json.dumps(item["details"], separators=(",", ":"))
        writer.writerow(item)
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=memoryos-enterprise-audit.csv"})


def run() -> None:
    import uvicorn

    settings = load_settings()
    uvicorn.run("enterprise.backend.app:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
