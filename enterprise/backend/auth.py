from __future__ import annotations

import hashlib
import hmac
from typing import Optional

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from .audit import now
from .config import load_settings
from .db import connect
from .schemas import Principal


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    return authorization.split(" ", 1)[1].strip()


def require_bootstrap_token(authorization: Optional[str] = Header(default=None)) -> None:
    settings = load_settings()
    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Enterprise mode is disabled.")
    if not settings.bootstrap_token:
        raise HTTPException(status_code=503, detail="Enterprise bootstrap token is not configured.")
    token = bearer_token(authorization)
    if not hmac.compare_digest(token, settings.bootstrap_token):
        raise HTTPException(status_code=403, detail="Invalid bootstrap token.")


def validate_oidc_token(token: str) -> dict:
    settings = load_settings()
    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Enterprise mode is disabled.")
    if settings.oidc_jwks_url and settings.oidc_issuer and settings.oidc_audience:
        signing_key = PyJWKClient(settings.oidc_jwks_url).get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
        )
    if settings.jwt_hs256_secret and settings.oidc_audience:
        kwargs = {"audience": settings.oidc_audience}
        if settings.oidc_issuer:
            kwargs["issuer"] = settings.oidc_issuer
        return jwt.decode(token, settings.jwt_hs256_secret, algorithms=["HS256"], **kwargs)
    raise HTTPException(status_code=503, detail="Enterprise SSO is not configured.")


def current_principal(authorization: Optional[str] = Header(default=None)) -> Principal:
    claims = validate_oidc_token(bearer_token(authorization))
    subject = str(claims.get("sub") or "")
    email = str(claims.get("email") or claims.get("upn") or "")
    name = str(claims.get("name") or email or subject)
    if not subject or not email:
        raise HTTPException(status_code=401, detail="SSO token must contain sub and email/upn claims.")

    settings = load_settings()
    org_slug = str(claims.get("memoryos_org") or claims.get("org") or claims.get("hd") or settings.default_org_slug)

    with connect() as conn:
        org = conn.execute("SELECT * FROM organizations WHERE slug = ?", (org_slug,)).fetchone()
        if not org:
            raise HTTPException(status_code=403, detail="Organization is not provisioned.")
        if org["sso_issuer"] and settings.oidc_issuer and org["sso_issuer"] != settings.oidc_issuer:
            raise HTTPException(status_code=403, detail="SSO issuer does not match organization configuration.")
        if org["sso_audience"] and settings.oidc_audience and org["sso_audience"] != settings.oidc_audience:
            raise HTTPException(status_code=403, detail="SSO audience does not match organization configuration.")
        organization_id = int(org["id"])

        user = conn.execute(
            "SELECT * FROM users WHERE organization_id = ? AND subject = ?",
            (organization_id, subject),
        ).fetchone()
        if not user or user["status"] != "active":
            raise HTTPException(status_code=403, detail="User is not provisioned for this organization.")
        user_id = int(user["id"])
        role = str(user["role"])
        conn.execute(
            "UPDATE users SET email = ?, name = ?, last_seen_at = ? WHERE id = ?",
            (email, name, now(), user_id),
        )
        conn.commit()

    return Principal(organization_id=organization_id, user_id=user_id, subject=subject, email=email, name=name, role=role)
