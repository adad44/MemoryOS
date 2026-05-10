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
    database_engine: str
    bootstrap_token: str
    oidc_issuer: str
    oidc_audience: str
    oidc_jwks_url: str
    jwt_hs256_secret: str
    default_org_slug: str
    scim_token: str
    scim_org_slug: str
    encryption_enabled: bool
    kms_provider: str
    kms_master_key: str
    kms_key_id: str
    kms_region: str
    search_index_key: str
    cors_origins: tuple[str, ...]


def load_settings() -> EnterpriseSettings:
    data_dir = Path(os.environ.get("MEMORYOS_ENTERPRISE_DATA_DIR", "~/.local/share/memoryos-enterprise")).expanduser()
    return EnterpriseSettings(
        enabled=os.environ.get("MEMORYOS_ENTERPRISE_ENABLED", "").lower() in {"1", "true", "yes"},
        host=os.environ.get("MEMORYOS_ENTERPRISE_HOST", "127.0.0.1"),
        port=int(os.environ.get("MEMORYOS_ENTERPRISE_PORT", "8775")),
        database_url=os.environ.get("MEMORYOS_ENTERPRISE_DATABASE_URL", os.environ.get("MEMORYOS_ENTERPRISE_DB", str(data_dir / "enterprise.db"))),
        database_engine=os.environ.get("MEMORYOS_ENTERPRISE_DATABASE_ENGINE", "sqlite").lower(),
        bootstrap_token=os.environ.get("MEMORYOS_ENTERPRISE_BOOTSTRAP_TOKEN", ""),
        oidc_issuer=os.environ.get("MEMORYOS_ENTERPRISE_OIDC_ISSUER", ""),
        oidc_audience=os.environ.get("MEMORYOS_ENTERPRISE_OIDC_AUDIENCE", ""),
        oidc_jwks_url=os.environ.get("MEMORYOS_ENTERPRISE_OIDC_JWKS_URL", ""),
        jwt_hs256_secret=os.environ.get("MEMORYOS_ENTERPRISE_JWT_HS256_SECRET", ""),
        default_org_slug=os.environ.get("MEMORYOS_ENTERPRISE_DEFAULT_ORG", "default"),
        scim_token=os.environ.get("MEMORYOS_ENTERPRISE_SCIM_TOKEN", ""),
        scim_org_slug=os.environ.get("MEMORYOS_ENTERPRISE_SCIM_ORG", os.environ.get("MEMORYOS_ENTERPRISE_DEFAULT_ORG", "default")),
        encryption_enabled=os.environ.get("MEMORYOS_ENTERPRISE_ENCRYPTION_ENABLED", "").lower() in {"1", "true", "yes"},
        kms_provider=os.environ.get("MEMORYOS_ENTERPRISE_KMS_PROVIDER", "local").lower(),
        kms_master_key=os.environ.get("MEMORYOS_ENTERPRISE_LOCAL_KMS_MASTER_KEY", os.environ.get("MEMORYOS_ENTERPRISE_KMS_MASTER_KEY", "")),
        kms_key_id=os.environ.get("MEMORYOS_ENTERPRISE_KMS_KEY_ID", "memoryos-enterprise-local"),
        kms_region=os.environ.get("MEMORYOS_ENTERPRISE_KMS_REGION", ""),
        search_index_key=os.environ.get("MEMORYOS_ENTERPRISE_SEARCH_INDEX_KEY", os.environ.get("MEMORYOS_ENTERPRISE_LOCAL_KMS_MASTER_KEY", os.environ.get("MEMORYOS_ENTERPRISE_KMS_MASTER_KEY", ""))),
        cors_origins=tuple(origin.strip() for origin in os.environ.get("MEMORYOS_ENTERPRISE_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",") if origin.strip()),
    )
