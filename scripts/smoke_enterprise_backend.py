#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import jwt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def request(method: str, url: str, data: dict[str, Any] | None = None, token: str | None = None, expect: int = 200) -> Any:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = response.read().decode("utf-8")
            if response.status != expect:
                raise AssertionError(f"{method} {url} expected {expect}, got {response.status}: {payload}")
            content_type = response.headers.get("content-type", "")
            return json.loads(payload) if payload and "json" in content_type else payload
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        if exc.code == expect:
            return {"status": exc.code, "body": payload}
        raise AssertionError(f"{method} {url} expected {expect}, got {exc.code}: {payload}") from exc


def token(secret: str, role: str, subject: str, email: str) -> str:
    return jwt.encode(
        {
            "sub": subject,
            "email": email,
            "name": email.split("@", 1)[0].title(),
            "memoryos_org": "acme",
            "memoryos_role": role,
            "aud": "memoryos-enterprise",
        },
        secret,
        algorithm="HS256",
    )


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="memoryos-enterprise-smoke-") as tmp:
        tmp_path = Path(tmp)
        enterprise_db = tmp_path / "enterprise.db"
        port = int(os.environ.get("MEMORYOS_ENTERPRISE_SMOKE_PORT") or free_port())
        base = f"http://127.0.0.1:{port}"
        bootstrap_token = secrets.token_urlsafe(32)
        jwt_secret = secrets.token_urlsafe(48)
        agent_token = secrets.token_urlsafe(32)
        scim_token = secrets.token_urlsafe(32)
        kms_key = secrets.token_urlsafe(48)

        env = os.environ.copy()
        env.update(
            {
                "PYTHONPATH": str(ROOT),
                "MEMORYOS_ENTERPRISE_ENABLED": "true",
                "MEMORYOS_ENTERPRISE_DB": str(enterprise_db),
                "MEMORYOS_ENTERPRISE_BOOTSTRAP_TOKEN": bootstrap_token,
                "MEMORYOS_ENTERPRISE_JWT_HS256_SECRET": jwt_secret,
                "MEMORYOS_ENTERPRISE_OIDC_AUDIENCE": "memoryos-enterprise",
                "MEMORYOS_ENTERPRISE_DEFAULT_ORG": "acme",
                "MEMORYOS_ENTERPRISE_PORT": str(port),
                "MEMORYOS_ENTERPRISE_SCIM_TOKEN": scim_token,
                "MEMORYOS_ENTERPRISE_SCIM_ORG": "acme",
                "MEMORYOS_ENTERPRISE_ENCRYPTION_ENABLED": "true",
                "MEMORYOS_ENTERPRISE_KMS_MASTER_KEY": kms_key,
                "MEMORYOS_ENTERPRISE_KMS_KEY_ID": "smoke-key",
            }
        )
        proc = subprocess.Popen(
            [sys.executable, "-m", "enterprise.backend.app"],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(80):
                try:
                    health = request("GET", f"{base}/health")
                    if health.get("ok"):
                        break
                except Exception:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Enterprise backend did not become healthy.")

            owner = token(jwt_secret, "owner", "owner-subject", "owner@acme.example")
            auditor = token(jwt_secret, "auditor", "auditor-subject", "auditor@acme.example")
            member = token(jwt_secret, "member", "member-subject", "member@acme.example")
            forged_member = token(jwt_secret, "owner", "member-subject", "member@acme.example")
            request("GET", f"{base}/auth/me", token=owner, expect=403)

            request(
                "POST",
                f"{base}/bootstrap",
                {
                    "organization_name": "Acme",
                    "organization_slug": "acme",
                    "owner_email": "owner@acme.example",
                    "owner_name": "Acme Owner",
                    "owner_subject": "owner-subject",
                },
                bootstrap_token,
            )
            request("GET", f"{base}/auth/me", token=owner)
            console = request("GET", f"{base}/admin/console")
            if "MemoryOS Teams Admin" not in console:
                raise AssertionError("Admin console did not render.")
            if "localStorage" in console:
                raise AssertionError("Admin console should not persist bearer tokens in localStorage.")
            scim_config = request("GET", f"{base}/scim/v2/ServiceProviderConfig")
            if not scim_config["patch"]["supported"]:
                raise AssertionError("SCIM service provider config is not valid.")
            member_principal = request(
                "POST",
                f"{base}/admin/users",
                {
                    "subject": "member-subject",
                    "email": "member@acme.example",
                    "name": "Member User",
                    "role": "member",
                },
                owner,
            )
            request(
                "POST",
                f"{base}/admin/users",
                {
                    "subject": "auditor-subject",
                    "email": "auditor@acme.example",
                    "name": "Auditor User",
                    "role": "auditor",
                },
                owner,
            )
            scim_user = request(
                "POST",
                f"{base}/scim/v2/Users",
                {
                    "userName": "scim@acme.example",
                    "externalId": "scim-subject",
                    "displayName": "SCIM User",
                    "active": True,
                    "emails": [{"value": "scim@acme.example", "primary": True}],
                },
                scim_token,
                expect=201,
            )
            if scim_user["userName"] != "scim@acme.example":
                raise AssertionError("SCIM user create failed.")
            scim_member = token(jwt_secret, "owner", "scim-subject", "scim@acme.example")
            if request("GET", f"{base}/auth/me", token=scim_member)["role"] != "member":
                raise AssertionError("SCIM-provisioned user did not authenticate with stored role.")
            scim_group = request(
                "POST",
                f"{base}/scim/v2/Groups",
                {
                    "displayName": "SCIM Product",
                    "externalId": "scim-product",
                    "members": [{"value": str(member_principal["id"])}],
                },
                scim_token,
                expect=201,
            )
            patched_group = request(
                "PATCH",
                f"{base}/scim/v2/Groups/{scim_group['id']}",
                {"Operations": [{"op": "Remove", "path": f"members[value eq \"{member_principal['id']}\"]"}]},
                scim_token,
            )
            if patched_group["members"]:
                raise AssertionError("SCIM filtered member remove did not update group memberships.")
            request("DELETE", f"{base}/scim/v2/Groups/{scim_group['id']}", token=scim_token, expect=204)
            member_me = request("GET", f"{base}/auth/me", token=forged_member)
            if member_me["role"] != "member":
                raise AssertionError("JWT role claim overrode provisioned member role.")
            team = request("POST", f"{base}/admin/teams", {"name": "Product"}, owner)
            project = request("POST", f"{base}/admin/projects", {"team_id": team["id"], "name": "Enterprise Pilot"}, owner)
            request(
                "PUT",
                f"{base}/admin/policy",
                {
                    "capture_sources": ["meetings", "docs", "tickets", "chat"],
                    "blocked_apps": ["Personal Notes"],
                    "blocked_domains": ["personal.example"],
                    "excluded_path_fragments": ["/Private"],
                    "redaction_terms": ["secret"],
                    "retention_days": 120,
                    "sync_enabled": True,
                    "require_explicit_share": True,
                },
                owner,
            )
            request(
                "PUT",
                f"{base}/admin/policy",
                {"retention_days": 90},
                auditor,
                expect=403,
            )
            device = request("POST", f"{base}/sync/devices", {"device_name": "Owner Mac", "trust_state": "trusted"}, owner)
            policy = request("GET", f"{base}/sync/policy?device_id={device['id']}", token=owner)
            if policy["privacy_settings"]["blocked_apps"] != ["Personal Notes"]:
                raise AssertionError("Policy sync did not render local privacy settings.")
            request("GET", f"{base}/sync/policy?device_id={device['id']}", token=member, expect=403)
            member_device = request("POST", f"{base}/sync/devices", {"device_name": "Member Mac", "trust_state": "trusted"}, member)
            if member_device["trust_state"] != "pending":
                raise AssertionError("Non-admin device registration should remain pending.")
            trusted_member_device = request("PUT", f"{base}/admin/devices/{member_device['id']}/trust", {"trust_state": "trusted"}, owner)
            if trusted_member_device["trust_state"] != "trusted":
                raise AssertionError("Admin device trust update failed.")

            shared = request(
                "POST",
                f"{base}/sync/share",
                {
                    "local_capture_id": 1,
                    "device_id": device["id"],
                    "content": "Launch blocker: rotate the secret before customer pilot.",
                    "team_id": team["id"],
                    "project_id": project["id"],
                    "title": "Contains secret title",
                    "summary": "Contains secret",
                    "app_name": "Slack",
                    "window_title": "Enterprise secret launch",
                    "source_type": "chat",
                    "url": "https://example.test/secret",
                    "metadata": {"note": "secret metadata"},
                },
                owner,
            )
            shared_text = json.dumps(shared).lower()
            if "secret" in shared_text:
                raise AssertionError("Shared memory was not redacted.")
            with sqlite3.connect(enterprise_db) as db:
                db.row_factory = sqlite3.Row
                encrypted_row = db.execute("SELECT title, summary, redacted_content, metadata, redacted_content_ciphertext, encrypted_dek, kms_key_id FROM shared_memories WHERE id = ?", (shared["id"],)).fetchone()
                if encrypted_row["title"] != "[encrypted]" or encrypted_row["summary"] != "[encrypted]" or encrypted_row["redacted_content"] != "[encrypted]" or encrypted_row["metadata"] != '{"encrypted":true}':
                    raise AssertionError("Shared memory payload fields were not envelope encrypted at rest.")
                if not encrypted_row["redacted_content_ciphertext"] or not encrypted_row["encrypted_dek"] or encrypted_row["kms_key_id"] != "smoke-key":
                    raise AssertionError("Shared memory envelope encryption metadata is incomplete.")
            request("GET", f"{base}/sync/shared?team_id={team['id']}", token=member, expect=403)
            request(
                "POST",
                f"{base}/admin/teams/{team['id']}/members",
                {"user_id": member_principal["id"], "role": "member"},
                owner,
            )
            member_shared = request("GET", f"{base}/sync/shared?team_id={team['id']}", token=member)
            if not member_shared:
                raise AssertionError("Team member could not read shared team memory.")

            grant = request(
                "POST",
                f"{base}/admin/agent-grants",
                {"agent_name": "Hermes Agent", "token": agent_token, "team_id": team["id"], "project_id": project["id"]},
                owner,
            )
            if grant["agent_name"] != "Hermes Agent":
                raise AssertionError("Hermes grant was not created.")
            request(
                "POST",
                f"{base}/admin/agent-grants",
                {"agent_name": "Hermes Agent", "token": secrets.token_urlsafe(32)},
                owner,
                expect=422,
            )
            request(
                "POST",
                f"{base}/admin/agent-grants",
                {"agent_name": "Hermes Agent", "token": secrets.token_urlsafe(32), "team_id": team["id"], "can_request_private": True},
                owner,
                expect=422,
            )

            context = request(
                "POST",
                f"{base}/agent/context",
                {"team_id": team["id"], "project_id": project["id"], "query": "launch", "limit": 5},
                agent_token,
            )
            if not context["shared_memories"]:
                raise AssertionError("Hermes Agent context did not include shared memory.")
            request(
                "POST",
                f"{base}/agent/context",
                {"team_id": team["id"] + 9999, "query": "launch"},
                agent_token,
                expect=403,
            )
            request(
                "POST",
                f"{base}/agent/context",
                {"team_id": team["id"], "project_id": project["id"], "include_private_recent": True},
                agent_token,
                expect=403,
            )

            audit_request = urllib.request.Request(
                f"{base}/audit/export?format=jsonl",
                headers={"Authorization": f"Bearer {auditor}"},
                method="GET",
            )
            audit_jsonl = urllib.request.urlopen(audit_request, timeout=10).read().decode("utf-8")
            for expected in ["memory_shared", "agent_context_read", "audit_exported"]:
                if expected not in audit_jsonl:
                    raise AssertionError(f"Audit export missing {expected}.")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    print("Enterprise backend smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
