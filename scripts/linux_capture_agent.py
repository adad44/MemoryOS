#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


ROOT = Path(__file__).resolve().parents[1]
ML_ROOT = ROOT / "ml"
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from memoryos.config import database_path, support_dir
from memoryos.db import connect


DEFAULT_EXTENSIONS = {
    "md",
    "txt",
    "py",
    "js",
    "ts",
    "tsx",
    "jsx",
    "json",
    "yaml",
    "yml",
    "html",
    "css",
    "csv",
    "go",
    "rs",
    "java",
    "kt",
    "sh",
    "zsh",
    "bash",
    "toml",
    "ini",
    "conf",
    "sql",
}


@dataclass
class PrivacyConfig:
    blocked_apps: set[str] = field(default_factory=set)
    blocked_domains: set[str] = field(default_factory=set)
    excluded_path_fragments: set[str] = field(default_factory=set)


@dataclass
class AgentConfig:
    poll_interval: float
    scan_interval: float
    min_capture_chars: int
    min_window_chars: int
    max_file_chars: int
    max_file_bytes: int
    watched_dirs: list[Path]
    allowed_extensions: set[str]
    pause_flag_path: Path
    capture_windows: bool
    capture_files: bool
    privacy: PrivacyConfig


def log(message: str) -> None:
    print(message, flush=True)


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def digest_parts(parts: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8", errors="ignore"))
        digest.update(b"\0")
    return digest.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_privacy(data_dir: Path) -> PrivacyConfig:
    defaults = PrivacyConfig(
        blocked_apps={"1Password", "Keychain", "KeePass", "Bitwarden"},
        blocked_domains={"bank", "chase.com", "wellsfargo.com", "capitalone.com", "paypal.com", "venmo.com"},
        excluded_path_fragments={"/.ssh/", "/.gnupg/", "/.password-store/", "/.local/share/keyrings/", "/.Trash/"},
    )
    path = data_dir / "privacy.json"
    if not path.exists():
        return defaults
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"warning: could not read privacy config at {path}: {exc}")
        return defaults

    return PrivacyConfig(
        blocked_apps=defaults.blocked_apps.union(data.get("blocked_apps") or []),
        blocked_domains=defaults.blocked_domains.union(data.get("blocked_domains") or []),
        excluded_path_fragments=defaults.excluded_path_fragments.union(data.get("excluded_path_fragments") or []),
    )


def default_watch_dirs() -> list[Path]:
    home = Path.home()
    candidates = [home / "Documents", home / "Desktop", home / "Downloads"]
    env_dirs = os.environ.get("MEMORYOS_LINUX_WATCH_DIRS")
    if env_dirs:
        candidates = [Path(item).expanduser() for item in env_dirs.split(":") if item.strip()]
    return [path for path in candidates if path.exists() and path.is_dir()]


def load_config(args: argparse.Namespace) -> AgentConfig:
    data_dir = support_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    watch_dirs = [Path(item).expanduser() for item in args.watch_dir] if args.watch_dir else default_watch_dirs()
    extensions = {
        item.strip().lower().lstrip(".")
        for item in os.environ.get("MEMORYOS_LINUX_FILE_EXTENSIONS", ",".join(sorted(DEFAULT_EXTENSIONS))).split(",")
        if item.strip()
    }
    return AgentConfig(
        poll_interval=float(args.poll_interval),
        scan_interval=float(args.scan_interval),
        min_capture_chars=int(args.min_chars),
        min_window_chars=int(args.min_window_chars),
        max_file_chars=int(args.max_file_chars),
        max_file_bytes=int(args.max_file_bytes),
        watched_dirs=watch_dirs,
        allowed_extensions=extensions,
        pause_flag_path=data_dir / "capture.paused",
        capture_windows=not args.no_window,
        capture_files=not args.no_files,
        privacy=load_privacy(data_dir),
    )


def is_paused(config: AgentConfig) -> bool:
    return config.pause_flag_path.exists()


def run_text(command: list[str], timeout: float = 2.0) -> Optional[str]:
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    value = result.stdout.strip()
    return value or None


def active_window_snapshot() -> Optional[tuple[str, str, str]]:
    if shutil.which("xdotool") is None:
        return None
    window_id = run_text(["xdotool", "getactivewindow"])
    if not window_id:
        return None
    title = run_text(["xdotool", "getwindowname", window_id]) or ""
    pid = run_text(["xdotool", "getwindowpid", window_id])
    app_name = "Linux Window"
    if pid:
        app_name = run_text(["ps", "-p", pid, "-o", "comm="]) or app_name
    content = normalize_text(f"Active window: {title}. Application: {app_name}.")
    return app_name, title, content


def should_skip_window(app_name: str, title: str, config: AgentConfig) -> bool:
    joined = f"{app_name} {title}".lower()
    if any(item.lower() in joined for item in config.privacy.blocked_apps):
        return True
    if any(item.lower() in joined for item in config.privacy.blocked_domains):
        return True
    return False


def insert_capture(
    *,
    app_name: str,
    window_title: Optional[str],
    content: str,
    source_type: str,
    url: Optional[str] = None,
    file_path: Optional[str] = None,
) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO captures
            (timestamp, app_name, window_title, content, source_type, url, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (now_iso(), app_name, window_title, content, source_type, url, file_path),
        )
        conn.commit()
        return int(cursor.lastrowid)


def path_is_excluded(path: Path, config: AgentConfig) -> bool:
    value = str(path)
    return any(fragment in value for fragment in config.privacy.excluded_path_fragments)


def should_capture_file(path: Path, config: AgentConfig) -> bool:
    if path.name.startswith("."):
        return False
    if path_is_excluded(path, config):
        return False
    if not path.is_file():
        return False
    if path.suffix.lower().lstrip(".") not in config.allowed_extensions:
        return False
    try:
        stat = path.stat()
    except OSError:
        return False
    return 0 < stat.st_size <= config.max_file_bytes


def read_file_text(path: Path, config: AgentConfig) -> Optional[str]:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data:
        return None
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        return None
    return normalize_text(text)[: config.max_file_chars]


class LinuxCaptureAgent:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.running = True
        self.last_window_digest: Optional[str] = None
        self.file_state: dict[Path, tuple[int, int]] = {}
        self.last_file_scan = 0.0

    def stop(self, *_: object) -> None:
        self.running = False

    def capture_window(self) -> None:
        snapshot = active_window_snapshot()
        if snapshot is None:
            return
        app_name, title, content = snapshot
        if len(content) < self.config.min_window_chars:
            return
        if should_skip_window(app_name, title, self.config):
            return
        digest = digest_parts([app_name, title, content])
        if digest == self.last_window_digest:
            return
        self.last_window_digest = digest
        insert_capture(app_name=app_name, window_title=title, content=content, source_type="linux_window")

    def scan_files(self) -> None:
        for base in self.config.watched_dirs:
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if not should_capture_file(path, self.config):
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                fingerprint = (int(stat.st_mtime), int(stat.st_size))
                if self.file_state.get(path) == fingerprint:
                    continue
                self.file_state[path] = fingerprint
                content = read_file_text(path, self.config)
                if not content or len(content) < self.config.min_capture_chars:
                    continue
                insert_capture(
                    app_name="File System",
                    window_title=path.name,
                    content=content,
                    source_type="file",
                    file_path=str(path),
                )

    def run_once(self) -> None:
        if is_paused(self.config):
            return
        if self.config.capture_windows:
            self.capture_window()
        if self.config.capture_files:
            self.scan_files()

    def run_forever(self) -> None:
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        if self.config.capture_windows and shutil.which("xdotool") is None:
            log("warning: xdotool is not installed; active-window capture is disabled.")
            log("warning: on Wayland, global active-window capture may be unavailable by design.")
        log("MemoryOS Linux capture agent starting")
        log(f"Database: {database_path()}")
        log(f"Watching: {', '.join(str(path) for path in self.config.watched_dirs) or '(none)'}")
        while self.running:
            if is_paused(self.config):
                time.sleep(self.config.poll_interval)
                continue
            if self.config.capture_windows:
                self.capture_window()
            if self.config.capture_files and time.monotonic() - self.last_file_scan >= self.config.scan_interval:
                self.scan_files()
                self.last_file_scan = time.monotonic()
            time.sleep(self.config.poll_interval)


def print_stats() -> None:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT app_name, COUNT(*) AS count
            FROM captures
            GROUP BY app_name
            ORDER BY count DESC
            LIMIT 20
            """
        ).fetchall()
    if not rows:
        print("No captures yet.")
        return
    for row in rows:
        print(f"{row['app_name']}: {row['count']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MemoryOS Linux capture agent.")
    parser.add_argument("--once", action="store_true", help="Capture once and exit.")
    parser.add_argument("--stats", action="store_true", help="Print capture counts by app and exit.")
    parser.add_argument("--no-window", action="store_true", help="Disable active-window title capture.")
    parser.add_argument("--no-files", action="store_true", help="Disable file polling capture.")
    parser.add_argument("--watch-dir", action="append", default=[], help="Directory to scan; can be used multiple times.")
    parser.add_argument("--poll-interval", default=os.environ.get("MEMORYOS_LINUX_POLL_SECONDS", "8"))
    parser.add_argument("--scan-interval", default=os.environ.get("MEMORYOS_LINUX_SCAN_SECONDS", "20"))
    parser.add_argument("--min-chars", default=os.environ.get("MEMORYOS_MIN_CAPTURE_CHARS", "180"))
    parser.add_argument("--min-window-chars", default=os.environ.get("MEMORYOS_MIN_WINDOW_CHARS", "20"))
    parser.add_argument("--max-file-chars", default=os.environ.get("MEMORYOS_MAX_FILE_CHARS", "2000"))
    parser.add_argument("--max-file-bytes", default=os.environ.get("MEMORYOS_MAX_FILE_BYTES", "262144"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args)
    if args.stats:
        print_stats()
        return 0
    agent = LinuxCaptureAgent(config)
    if args.once:
        agent.run_once()
        return 0
    agent.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
