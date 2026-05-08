from __future__ import annotations

import os
import platform
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ML_ROOT = PROJECT_ROOT / "ml"


def support_dir() -> Path:
    override = os.environ.get("MEMORYOS_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if platform.system() == "Darwin":
        return Path("~/Library/Application Support/MemoryOS").expanduser()
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / "memoryos"
    return Path("~/.local/share/memoryos").expanduser()


def database_path() -> Path:
    override = os.environ.get("MEMORYOS_DB")
    if override:
        return Path(override).expanduser()
    return support_dir() / "memoryos.db"


MODEL_DIR = support_dir() / "models"
PROCESSED_DIR = support_dir() / "data" / "processed"


def ensure_dirs() -> None:
    support_dir().mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
