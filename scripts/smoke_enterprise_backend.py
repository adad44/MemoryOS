#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import secrets
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

from ml.memoryos.db import connect as connect_local_memory  # noqa: E402


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
            return json.loads(payload) if payload else {}
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="memoryos-enterprise-smoke-") as tmp:
        tmp_path = Path(tmp)
        enterprise_db = tmp_path / "enterprise.db"
        local_db = tmp_path / "local-memoryos.db"
        port = int(os.environ.get("MEMORYOS_ENTERPRISE_SMOKE_PORT", "8899"))
        base = f"http://127.0.0.1:{port}"
        bootstrap_token = secrets.token_urlsafe(32)
        jwt_secret = secrets.token_urlsafe(48)
        agent_token = secrets.token_urlsafe(32)

        with connect_local_memory(local_db) as conn:
            conn.execute(
                """
                INSERT INTO captures (timestamp, app_name, window_title, content, source_type, url, file_path, is_noise, is_pinned)
                VALUES (CURRENT_TIMESTAMP, 'Slack', 'Enterprise launch', ?, 'chat', NULL, NULL, 0, 0)
                """,
                ("Launch blocker: rotate the secret before customer pilot.",),
            )
            conn.commit()

        env = os.environ.copy()
        env.update(
            {
                "PYTHONPATH": str(ROOT),
                "MEMORYOS_ENTERPRISE_ENABLED": "true",
                "MEMORYOS_ENTERPRISE_DB": str(enterprise_db),
                "MEMORYOS_LOCAL_DB": str(local_db),
                "MEMORYOS_ENTERPRISE_BOOTSTRAP_TOKEN": bootstrap_token,
                "MEMORYOS_ENTERPRISE_JWT_HS256_SECRET": jwt_secret,
                "MEMORYOS_ENTERPRISE_OIDC_AUDIENCE": "memoryos-enterprise",
                "MEMORYOS_ENTERPRISE_DEFAULT_ORG": "acme",
                "MEMORYOS_ENTERPRISE_PORT": str(port),
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

            shared = request(
                "POST",
                f"{base}/sync/share",
                {"local_capture_id": 1, "team_id": team["id"], "project_id": project["id"], "summary": "Contains secret"},
                owner,
            )
            if "secret" in shared["summary"].lower() or "secret" in shared["redacted_content"].lower():
                raise AssertionError("Shared memory was not redacted.")

            grant = request(
                "POST",
                f"{base}/admin/agent-grants",
                {"agent_name": "Hermes Agent", "token": agent_token, "team_id": team["id"], "project_id": project["id"]},
                owner,
            )
            if grant["agent_name"] != "Hermes Agent":
                raise AssertionError("Hermes grant was not created.")

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

            audit_request = urllib.request.Request(
                f"{base}/audit/export?format=jsonl",
                headers={"Authorization": f"Bearer {auditor}"},
                method="GET",
            )
            urllib.request.urlopen(audit_request, timeout=10).read()
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
