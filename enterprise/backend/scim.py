from __future__ import annotations

import hmac
import re
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .audit import log_event, row_dict
from .auth import bearer_token
from .config import load_settings
from .db import connect


router = APIRouter(prefix="/scim/v2", tags=["SCIM"])


class ScimName(BaseModel):
    givenName: Optional[str] = None
    familyName: Optional[str] = None
    formatted: Optional[str] = None


class ScimEmail(BaseModel):
    value: str
    primary: bool = True


class ScimUserRequest(BaseModel):
    userName: str = Field(min_length=1)
    externalId: Optional[str] = None
    name: Optional[ScimName] = None
    displayName: Optional[str] = None
    active: bool = True
    emails: list[ScimEmail] = Field(default_factory=list)


class ScimGroupRequest(BaseModel):
    displayName: str = Field(min_length=1)
    externalId: Optional[str] = None
    members: list[dict[str, Any]] = Field(default_factory=list)


def require_scim(authorization: Optional[str]) -> int:
    settings = load_settings()
    if not settings.scim_token:
        raise HTTPException(status_code=503, detail="SCIM token is not configured.")
    token = bearer_token(authorization)
    if not hmac.compare_digest(token, settings.scim_token):
        raise HTTPException(status_code=403, detail="Invalid SCIM token.")
    with connect() as conn:
        org = conn.execute("SELECT id FROM organizations WHERE slug = ?", (settings.scim_org_slug,)).fetchone()
        if not org:
            raise HTTPException(status_code=404, detail="SCIM organization is not provisioned.")
        return int(org["id"])


def scim_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": str(row["id"]),
        "externalId": row.get("external_id") or row["subject"],
        "userName": row["email"],
        "displayName": row["name"],
        "active": row["status"] == "active",
        "emails": [{"value": row["email"], "primary": True}],
        "meta": {"resourceType": "User"},
    }


def scim_group(row: dict[str, Any], members: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
        "id": str(row["id"]),
        "externalId": row.get("external_id") or str(row["id"]),
        "displayName": row["name"],
        "members": members,
        "meta": {"resourceType": "Group"},
    }


@router.get("/ServiceProviderConfig")
def service_provider_config() -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "patch": {"supported": True},
        "bulk": {"supported": False},
        "filter": {"supported": True, "maxResults": 200},
        "changePassword": {"supported": False},
        "sort": {"supported": False},
        "etag": {"supported": False},
        "authenticationSchemes": [{"type": "oauthbearertoken", "name": "Bearer"}],
    }


@router.get("/ResourceTypes")
def resource_types() -> dict[str, Any]:
    resources = [
        {"id": "User", "name": "User", "endpoint": "/Users", "schema": "urn:ietf:params:scim:schemas:core:2.0:User"},
        {"id": "Group", "name": "Group", "endpoint": "/Groups", "schema": "urn:ietf:params:scim:schemas:core:2.0:Group"},
    ]
    return {"Resources": resources, "totalResults": len(resources), "itemsPerPage": len(resources), "startIndex": 1}


@router.get("/Schemas")
def schemas() -> dict[str, Any]:
    resources = [
        {"id": "urn:ietf:params:scim:schemas:core:2.0:User", "name": "User"},
        {"id": "urn:ietf:params:scim:schemas:core:2.0:Group", "name": "Group"},
    ]
    return {"Resources": resources, "totalResults": len(resources), "itemsPerPage": len(resources), "startIndex": 1}


@router.get("/Users")
def list_users(
    filter: Optional[str] = Query(default=None),
    startIndex: int = 1,
    count: int = 100,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    org_id = require_scim(authorization)
    with connect() as conn:
        params: list[Any] = [org_id]
        where = "organization_id = ?"
        if filter and "userName" in filter and "eq" in filter:
            value = filter.split("eq", 1)[1].strip().strip('"')
            where += " AND email = ?"
            params.append(value)
        rows = [scim_user(row_dict(row)) for row in conn.execute(f"SELECT * FROM users WHERE {where} ORDER BY id LIMIT ? OFFSET ?", [*params, count, max(startIndex - 1, 0)])]
        total = conn.execute(f"SELECT COUNT(*) AS count FROM users WHERE {where}", params).fetchone()["count"]
        return {"schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"], "Resources": rows, "totalResults": total, "itemsPerPage": len(rows), "startIndex": startIndex}


@router.post("/Users", status_code=201)
def create_user(request: ScimUserRequest, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    org_id = require_scim(authorization)
    email = request.emails[0].value if request.emails else request.userName
    name = request.displayName or (request.name.formatted if request.name and request.name.formatted else email)
    subject = request.externalId or request.userName
    status = "active" if request.active else "suspended"
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (organization_id, subject, external_id, email, name, role, status)
            VALUES (?, ?, ?, ?, ?, 'member', ?)
            """,
            (org_id, subject, request.externalId, email, name, status),
        )
        user_id = int(cursor.lastrowid)
        log_event(conn, org_id, None, "scim", "scim_user_created", "user", user_id, {"email": email, "status": status})
        conn.commit()
        return scim_user(row_dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()))


@router.get("/Users/{user_id}")
def get_user(user_id: int, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    org_id = require_scim(authorization)
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ? AND organization_id = ?", (user_id, org_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="SCIM user not found.")
        return scim_user(row_dict(row))


@router.patch("/Users/{user_id}")
def patch_user(user_id: int, payload: dict[str, Any], authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    org_id = require_scim(authorization)
    active: Optional[bool] = None
    display_name: Optional[str] = None
    for operation in payload.get("Operations", []):
        path = str(operation.get("path", "")).lower()
        value = operation.get("value")
        if path == "active":
            active = bool(value)
        if path in {"displayname", "name.formatted"} and value:
            display_name = str(value)
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ? AND organization_id = ?", (user_id, org_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="SCIM user not found.")
        if active is not None:
            conn.execute("UPDATE users SET status = ? WHERE id = ?", ("active" if active else "suspended", user_id))
        if display_name:
            conn.execute("UPDATE users SET name = ? WHERE id = ?", (display_name, user_id))
        log_event(conn, org_id, None, "scim", "scim_user_patched", "user", user_id, {"active": active, "display_name": bool(display_name)})
        conn.commit()
        return scim_user(row_dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()))


@router.delete("/Users/{user_id}", status_code=204)
def delete_user(user_id: int, authorization: Optional[str] = Header(default=None)) -> None:
    org_id = require_scim(authorization)
    with connect() as conn:
        conn.execute("UPDATE users SET status = 'suspended' WHERE id = ? AND organization_id = ?", (user_id, org_id))
        log_event(conn, org_id, None, "scim", "scim_user_suspended", "user", user_id)
        conn.commit()


@router.get("/Groups")
def list_groups(authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    org_id = require_scim(authorization)
    with connect() as conn:
        groups = []
        for row in conn.execute("SELECT * FROM teams WHERE organization_id = ? ORDER BY id", (org_id,)):
            members = [
                {"value": str(member["user_id"])}
                for member in conn.execute("SELECT user_id FROM team_memberships WHERE team_id = ?", (row["id"],))
            ]
            groups.append(scim_group(row_dict(row), members))
        return {"schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"], "Resources": groups, "totalResults": len(groups), "itemsPerPage": len(groups), "startIndex": 1}


@router.post("/Groups", status_code=201)
def create_group(request: ScimGroupRequest, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    org_id = require_scim(authorization)
    with connect() as conn:
        cursor = conn.execute("INSERT INTO teams (organization_id, external_id, name, description) VALUES (?, ?, ?, ?)", (org_id, request.externalId, request.displayName, "SCIM managed group"))
        team_id = int(cursor.lastrowid)
        for member in request.members:
            if "value" in member:
                conn.execute("INSERT OR IGNORE INTO team_memberships (team_id, user_id, role) VALUES (?, ?, 'member')", (team_id, int(member["value"])))
        log_event(conn, org_id, None, "scim", "scim_group_created", "team", team_id, {"displayName": request.displayName})
        conn.commit()
        row = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        members = [{"value": str(member["user_id"])} for member in conn.execute("SELECT user_id FROM team_memberships WHERE team_id = ?", (team_id,))]
        return scim_group(row_dict(row), members)


@router.get("/Groups/{group_id}")
def get_group(group_id: int, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    org_id = require_scim(authorization)
    with connect() as conn:
        row = conn.execute("SELECT * FROM teams WHERE id = ? AND organization_id = ?", (group_id, org_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="SCIM group not found.")
        members = [{"value": str(member["user_id"])} for member in conn.execute("SELECT user_id FROM team_memberships WHERE team_id = ?", (group_id,))]
        return scim_group(row_dict(row), members)


@router.patch("/Groups/{group_id}")
def patch_group(group_id: int, payload: dict[str, Any], authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    org_id = require_scim(authorization)
    with connect() as conn:
        row = conn.execute("SELECT * FROM teams WHERE id = ? AND organization_id = ?", (group_id, org_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="SCIM group not found.")
        for operation in payload.get("Operations", []):
            op = str(operation.get("op", "")).lower()
            path = str(operation.get("path", "")).lower()
            value = operation.get("value")
            if path == "displayname" and value:
                conn.execute("UPDATE teams SET name = ? WHERE id = ?", (str(value), group_id))
            if path.startswith("members") and isinstance(value, list):
                for member in value:
                    if "value" not in member:
                        continue
                    user_id = int(member["value"])
                    if op == "remove":
                        conn.execute("DELETE FROM team_memberships WHERE team_id = ? AND user_id = ?", (group_id, user_id))
                    else:
                        conn.execute("INSERT OR IGNORE INTO team_memberships (team_id, user_id, role) VALUES (?, ?, 'member')", (group_id, user_id))
            if op == "remove" and path.startswith("members["):
                match = re.search(r'value\s+eq\s+"?([^"\]]+)"?', path)
                if match:
                    conn.execute("DELETE FROM team_memberships WHERE team_id = ? AND user_id = ?", (group_id, int(match.group(1))))
        log_event(conn, org_id, None, "scim", "scim_group_patched", "team", group_id)
        conn.commit()
        row = conn.execute("SELECT * FROM teams WHERE id = ?", (group_id,)).fetchone()
        members = [{"value": str(member["user_id"])} for member in conn.execute("SELECT user_id FROM team_memberships WHERE team_id = ?", (group_id,))]
        return scim_group(row_dict(row), members)


@router.delete("/Groups/{group_id}", status_code=204)
def delete_group(group_id: int, authorization: Optional[str] = Header(default=None)) -> None:
    org_id = require_scim(authorization)
    with connect() as conn:
        project_ids = [int(row["id"]) for row in conn.execute("SELECT id FROM projects WHERE team_id = ?", (group_id,))]
        if project_ids:
            placeholders = ",".join(["?"] * len(project_ids))
            conn.execute(f"DELETE FROM project_memberships WHERE project_id IN ({placeholders})", project_ids)
        conn.execute("DELETE FROM team_memberships WHERE team_id = ?", (group_id,))
        conn.execute("UPDATE teams SET description = COALESCE(description, '') || ' [SCIM suspended]' WHERE id = ? AND organization_id = ?", (group_id, org_id))
        log_event(conn, org_id, None, "scim", "scim_group_suspended", "team", group_id)
        conn.commit()
