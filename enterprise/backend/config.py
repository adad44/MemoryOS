from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class EnterpriseSettings:
    enabled: bool
    host: str
    port: int
    database_url: str
    local_memoryos_db: str
    bootstrap_token: str
    oidc_issuer: str
    oidc_audience: str
    oidc_jwks_url: str
    jwt_hs256_secret: str
    default_org_slug: str


def load_settings() -> EnterpriseSettings:
    data_dir = Path(os.environ.get("MEMORYOS_ENTERPRISE_DATA_DIR", "~/.local/share/memoryos-enterprise")).expanduser()
    return EnterpriseSettings(
        enabled=os.environ.get("MEMORYOS_ENTERPRISE_ENABLED", "").lower() in {"1", "true", "yes"},
        host=os.environ.get("MEMORYOS_ENTERPRISE_HOST", "127.0.0.1"),
        port=int(os.environ.get("MEMORYOS_ENTERPRISE_PORT", "8775")),
        database_url=os.environ.get("MEMORYOS_ENTERPRISE_DB", str(data_dir / "enterprise.db")),
        local_memoryos_db=os.environ.get("MEMORYOS_LOCAL_DB", os.environ.get("MEMORYOS_DB", "")),
        bootstrap_token=os.environ.get("MEMORYOS_ENTERPRISE_BOOTSTRAP_TOKEN", ""),
        oidc_issuer=os.environ.get("MEMORYOS_ENTERPRISE_OIDC_ISSUER", ""),
        oidc_audience=os.environ.get("MEMORYOS_ENTERPRISE_OIDC_AUDIENCE", ""),
        oidc_jwks_url=os.environ.get("MEMORYOS_ENTERPRISE_OIDC_JWKS_URL", ""),
        jwt_hs256_secret=os.environ.get("MEMORYOS_ENTERPRISE_JWT_HS256_SECRET", ""),
        default_org_slug=os.environ.get("MEMORYOS_ENTERPRISE_DEFAULT_ORG", "default"),
    )

