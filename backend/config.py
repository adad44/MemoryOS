from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class BackendSettings:
    host: str
    port: int
    cors_origins: tuple[str, ...]
    index_interval_seconds: int
    index_backend: str
    index_model: Optional[str]


def load_settings() -> BackendSettings:
    origins = os.environ.get(
        "MEMORYOS_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return BackendSettings(
        host=os.environ.get("MEMORYOS_HOST", "127.0.0.1"),
        port=int(os.environ.get("MEMORYOS_PORT", "8765")),
        cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
        index_interval_seconds=int(os.environ.get("MEMORYOS_INDEX_INTERVAL_SECONDS", "1800")),
        index_backend=os.environ.get("MEMORYOS_INDEX_BACKEND", "auto"),
        index_model=os.environ.get("MEMORYOS_INDEX_MODEL"),
    )
