from __future__ import annotations

import json
import sqlite3
from typing import Any

from .audit import now
from .schemas import EnterprisePolicy


def json_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    try:
        parsed = json.loads(str(value))
    except Exception:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def json_text(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def policy_from_row(row: sqlite3.Row) -> EnterprisePolicy:
    return EnterprisePolicy(
        version=int(row["version"]),
        capture_sources=json_list(row["capture_sources"]),
        blocked_apps=json_list(row["blocked_apps"]),
        blocked_domains=json_list(row["blocked_domains"]),
        excluded_path_fragments=json_list(row["excluded_path_fragments"]),
        redaction_terms=json_list(row["redaction_terms"]),
        retention_days=int(row["retention_days"]),
        sync_enabled=bool(row["sync_enabled"]),
        require_explicit_share=bool(row["require_explicit_share"]),
        published_at=str(row["published_at"]),
    )


def default_policy() -> EnterprisePolicy:
    return EnterprisePolicy()


def active_policy(conn: sqlite3.Connection, organization_id: int) -> EnterprisePolicy:
    row = conn.execute(
        "SELECT * FROM policies WHERE organization_id = ? ORDER BY version DESC LIMIT 1",
        (organization_id,),
    ).fetchone()
    if row:
        return policy_from_row(row)
    return publish_policy(conn, organization_id, default_policy(), None)


def publish_policy(
    conn: sqlite3.Connection,
    organization_id: int,
    policy: EnterprisePolicy,
    published_by_user_id: int | None,
) -> EnterprisePolicy:
    row = conn.execute("SELECT MAX(version) AS version FROM policies WHERE organization_id = ?", (organization_id,)).fetchone()
    next_version = int(row["version"] or 0) + 1
    conn.execute(
        """
        INSERT INTO policies
        (organization_id, version, capture_sources, blocked_apps, blocked_domains, excluded_path_fragments,
         redaction_terms, retention_days, sync_enabled, require_explicit_share, published_by_user_id, published_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id,
            next_version,
            json_text(policy.capture_sources),
            json_text(policy.blocked_apps),
            json_text(policy.blocked_domains),
            json_text(policy.excluded_path_fragments),
            json_text(policy.redaction_terms),
            policy.retention_days,
            1 if policy.sync_enabled else 0,
            1 if policy.require_explicit_share else 0,
            published_by_user_id,
            now(),
        ),
    )
    return active_policy(conn, organization_id)


def render_local_privacy_settings(policy: EnterprisePolicy) -> dict[str, list[str]]:
    return {
        "blocked_apps": policy.blocked_apps,
        "blocked_domains": policy.blocked_domains,
        "excluded_path_fragments": policy.excluded_path_fragments,
    }


def render_local_storage_policy(policy: EnterprisePolicy) -> dict[str, object]:
    return {
        "mode": "enterprise",
        "retention_days": policy.retention_days,
        "auto_noise_enabled": True,
        "keep_clicked": True,
        "protect_keep_labels": True,
    }


def redact(text: str, policy: EnterprisePolicy) -> str:
    redacted = text
    for term in policy.redaction_terms:
        clean = term.strip()
        if not clean:
            continue
        for candidate in {clean, clean.lower(), clean.upper(), clean.title()}:
            redacted = redacted.replace(candidate, "[redacted]")
    return redacted

