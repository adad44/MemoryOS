from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Optional

from .config import PROJECT_ROOT

ML_ROOT = PROJECT_ROOT / "ml"
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from memoryos.config import database_path
from memoryos.db import CAPTURE_COLUMNS, connect, fetch_captures
from memoryos.features import normalize_text, result_snippet
from memoryos.index import (
    DEFAULT_EMBEDDER,
    FAISS_INDEX_PATH,
    FAISS_MAPPING_PATH,
    INDEX_ARTIFACT_PATH,
    build_index,
    index_backend,
    search_index,
)
from memoryos.reranker import rerank_hits

from .schemas import CaptureResult
from .schemas import CollectionSummary
from .schemas import CleanupResponse
from .schemas import PrivacySettings
from .schemas import StoragePolicy
from .schemas import TodoItem


def row_to_capture_result(
    row: sqlite3.Row,
    score: Optional[float] = None,
    rank: Optional[int] = None,
    similarity_score: Optional[float] = None,
    rerank_score: Optional[float] = None,
) -> CaptureResult:
    content = str(row["content"] or "")
    return CaptureResult(
        id=int(row["id"]),
        score=score,
        similarity_score=similarity_score,
        rerank_score=rerank_score,
        rank=rank,
        timestamp=str(row["timestamp"]),
        app_name=str(row["app_name"]),
        window_title=row["window_title"],
        content=content,
        snippet=result_snippet(content),
        source_type=str(row["source_type"]),
        url=row["url"],
        file_path=row["file_path"],
        is_noise=row["is_noise"],
        is_pinned=int(row["is_pinned"] or 0),
    )


def _support_dir() -> Path:
    support = Path.home() / "Library" / "Application Support" / "MemoryOS"
    support.mkdir(parents=True, exist_ok=True)
    return support


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _database_size_bytes() -> int:
    db_path = database_path()
    return sum(_path_size(Path(str(db_path) + suffix)) for suffix in ("", "-wal", "-shm"))


def _index_size_bytes() -> int:
    model_dir = PROJECT_ROOT / "ml" / "models"
    return _path_size(model_dir)


def _log_size_bytes() -> int:
    return _path_size(PROJECT_ROOT / ".logs")


def _protected_capture_ids(conn: sqlite3.Connection, policy: StoragePolicy) -> set[int]:
    protected: set[int] = set()
    protected.update(int(row["id"]) for row in conn.execute("SELECT id FROM captures WHERE is_pinned = 1"))
    if policy.protect_keep_labels:
        protected.update(int(row["id"]) for row in conn.execute("SELECT id FROM captures WHERE is_noise = 0"))
    if policy.keep_clicked:
        protected.update(int(row["capture_id"]) for row in conn.execute("SELECT DISTINCT capture_id FROM search_clicks"))
    return protected


def _storage_policy_path() -> Path:
    return _support_dir() / "storage_policy.json"


DEFAULT_STORAGE_POLICY = StoragePolicy(
    mode="balanced",
    auto_noise_enabled=True,
    min_text_chars=180,
    retention_days=30,
    noise_retention_hours=24,
    max_database_mb=1024,
    keep_clicked=True,
    protect_keep_labels=True,
    noise_apps=["Netflix", "Spotify", "TV", "Music", "Steam", "Games"],
    noise_domains=["netflix.com", "youtube.com", "youtu.be", "tiktok.com", "instagram.com", "spotify.com"],
)


def get_storage_policy() -> StoragePolicy:
    path = _storage_policy_path()
    if not path.exists():
        return DEFAULT_STORAGE_POLICY
    data = json.loads(path.read_text(encoding="utf-8"))
    defaults = DEFAULT_STORAGE_POLICY.dict()
    defaults.update(data)
    return StoragePolicy(**defaults)


def save_storage_policy(policy: StoragePolicy) -> StoragePolicy:
    presets = {
        "light": {"retention_days": 7, "noise_retention_hours": 12, "max_database_mb": 512},
        "balanced": {"retention_days": 30, "noise_retention_hours": 24, "max_database_mb": 1024},
        "deep": {"retention_days": 90, "noise_retention_hours": 72, "max_database_mb": 4096},
        "archive": {"retention_days": 3650, "noise_retention_hours": 168, "max_database_mb": 20_000},
    }
    if policy.mode in presets and policy.mode != get_storage_policy().mode:
        policy = policy.copy(update=presets[policy.mode])
    _storage_policy_path().write_text(json.dumps(policy.dict(), indent=2), encoding="utf-8")
    return policy


def _host_from_url(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def should_skip_capture(app_name: str, title: Optional[str], content: str, url: Optional[str], policy: StoragePolicy) -> bool:
    text = normalize_text(content)
    if len(text) < policy.min_text_chars:
        return True
    joined = " ".join([app_name or "", title or "", _host_from_url(url)]).lower()
    if any(item.lower() in joined for item in policy.noise_apps):
        return True
    return False


def auto_noise_label(app_name: str, title: Optional[str], content: str, url: Optional[str], policy: StoragePolicy) -> Optional[int]:
    if not policy.auto_noise_enabled:
        return None
    host = _host_from_url(url)
    joined = " ".join([app_name or "", title or "", host]).lower()
    if any(item.lower() in joined for item in policy.noise_apps):
        return 1
    if any(fragment.lower() in host for fragment in policy.noise_domains):
        return 1
    text = normalize_text(content)
    alpha_ratio = sum(char.isalpha() for char in text) / max(len(text), 1)
    if len(text) < policy.min_text_chars or alpha_ratio < 0.25:
        return 1
    return None


def search(query: str, top_k: int, candidate_k: int = 50) -> dict:
    started = time.perf_counter()
    if not INDEX_ARTIFACT_PATH.exists():
        raise FileNotFoundError("Search index is missing. Run /refresh-index or ml/train/build_index.py first.")
    with connect() as conn:
        rows = fetch_captures(conn, non_noise=True)
    rows_by_id = {int(row["id"]): row for row in rows}
    candidate_limit = max(top_k, candidate_k)
    hits = search_index(query, rows_by_id, top_k=candidate_limit)
    ranked_hits, reranker_name = rerank_hits(query, hits)
    results = []
    for rank, (hit, rerank_score) in enumerate(ranked_hits[:top_k], start=1):
        results.append(
            row_to_capture_result(
                hit.row,
                score=rerank_score,
                rank=rank,
                similarity_score=hit.score,
                rerank_score=rerank_score,
            )
        )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "results": results,
        "candidate_count": len(hits),
        "elapsed_ms": round(elapsed_ms, 2),
        "index_backend": index_backend(),
        "reranker": reranker_name,
    }


def recent(limit: int, app_name: Optional[str] = None, source_type: Optional[str] = None) -> list[CaptureResult]:
    where = []
    params: list[object] = []
    if app_name:
        where.append("app_name = ?")
        params.append(app_name)
    if source_type:
        where.append("source_type = ?")
        params.append(source_type)

    sql = f"SELECT {CAPTURE_COLUMNS} FROM captures"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_capture_result(row) for row in rows]


def stats() -> dict:
    db_path = database_path()
    with connect() as conn:
        total = int(conn.execute("SELECT COUNT(*) AS count FROM captures").fetchone()["count"])
        by_app = [
            {"app_name": row["app_name"], "count": int(row["count"])}
            for row in conn.execute(
                """
                SELECT app_name, COUNT(*) AS count
                FROM captures
                GROUP BY app_name
                ORDER BY count DESC
                LIMIT 20
                """
            )
        ]
        by_source = [
            {"source_type": row["source_type"], "count": int(row["count"])}
            for row in conn.execute(
                """
                SELECT source_type, COUNT(*) AS count
                FROM captures
                GROUP BY source_type
                ORDER BY count DESC
                """
            )
        ]
        noise_counts = [
            {"is_noise": row["is_noise"], "count": int(row["count"])}
            for row in conn.execute(
                """
                SELECT is_noise, COUNT(*) AS count
                FROM captures
                GROUP BY is_noise
                ORDER BY is_noise
                """
            )
        ]
        latest = conn.execute("SELECT MAX(timestamp) AS latest FROM captures").fetchone()["latest"]
        protected = len(_protected_capture_ids(conn, get_storage_policy()))

    return {
        "database_path": str(db_path),
        "total_captures": total,
        "indexed_available": INDEX_ARTIFACT_PATH.exists(),
        "counts_by_app": by_app,
        "counts_by_source_type": by_source,
        "noise_counts": noise_counts,
        "latest_capture_at": latest,
        "storage_bytes": _database_size_bytes() + _index_size_bytes() + _log_size_bytes(),
        "protected_captures": protected,
    }


def _timestamp_from_browser(value: Optional[float]) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    return datetime.fromtimestamp(float(value) / 1000, timezone.utc).isoformat()


def insert_browser_capture(url: Optional[str], title: Optional[str], content: str, timestamp: Optional[float]) -> int:
    cleaned = normalize_text(content)[:3_000]
    policy = get_storage_policy()
    if should_skip_capture("Browser", title, cleaned, url, policy):
        return 0
    label = auto_noise_label("Browser", title, cleaned, url, policy)
    with connect() as conn:
        duplicate = conn.execute(
            """
            SELECT id FROM captures
            WHERE source_type = 'browser'
              AND COALESCE(url, '') = COALESCE(?, '')
              AND COALESCE(window_title, '') = COALESCE(?, '')
              AND content = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (url, title, cleaned),
        ).fetchone()
        if duplicate:
            return int(duplicate["id"])
        cursor = conn.execute(
            """
            INSERT INTO captures
            (timestamp, app_name, window_title, content, source_type, url, file_path, is_noise)
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (_timestamp_from_browser(timestamp), "Browser", title, cleaned, "browser", url, label),
        )
        conn.commit()
        return int(cursor.lastrowid)


def refresh_index(backend: str, model: Optional[str], limit: Optional[int]) -> tuple[int, str, str]:
    with connect() as conn:
        rows = fetch_captures(conn, limit=limit, non_noise=True)
    artifact_path = build_index(
        rows,
        model_name=model or DEFAULT_EMBEDDER,
        backend=backend,
    )
    return len(rows), str(artifact_path), index_backend()


def log_search_click(query: str, capture_id: int, rank: Optional[int], dwell_ms: Optional[int] = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO search_clicks (query, capture_id, rank, dwell_ms) VALUES (?, ?, ?, ?)",
            (query, capture_id, rank, dwell_ms),
        )
        conn.commit()


def open_capture(capture_id: int) -> str:
    with connect() as conn:
        row = conn.execute(
            f"SELECT {CAPTURE_COLUMNS} FROM captures WHERE id = ?",
            (capture_id,),
        ).fetchone()
    if row is None:
        raise ValueError("Capture not found.")

    target = row["url"] or row["file_path"]
    if not target:
        raise ValueError("Capture has no URL or file path to open.")

    subprocess.run(["open", str(target)], check=True)
    return str(target)


def update_capture_noise_label(capture_id: int, is_noise: Optional[int]) -> bool:
    if is_noise not in (None, 0, 1):
        raise ValueError("is_noise must be null, 0, or 1.")
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE captures SET is_noise = ? WHERE id = ?",
            (is_noise, capture_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def update_capture_noise_labels(capture_ids: list[int], is_noise: Optional[int]) -> int:
    if is_noise not in (None, 0, 1):
        raise ValueError("is_noise must be null, 0, or 1.")
    unique_ids = sorted({int(capture_id) for capture_id in capture_ids})
    if not unique_ids:
        return 0
    placeholders = ",".join("?" for _ in unique_ids)
    with connect() as conn:
        cursor = conn.execute(
            f"UPDATE captures SET is_noise = ? WHERE id IN ({placeholders})",
            [is_noise, *unique_ids],
        )
        conn.commit()
        return int(cursor.rowcount)


def update_capture_pin(capture_id: int, is_pinned: bool) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE captures SET is_pinned = ? WHERE id = ?",
            (1 if is_pinned else 0, capture_id),
        )
        conn.commit()
        return cursor.rowcount > 0


COLLECTION_DEFINITIONS = [
    {
        "id": "pinned",
        "name": "Pinned",
        "description": "Memories the user explicitly pinned.",
        "where": "is_pinned = 1",
        "params": [],
    },
    {
        "id": "papers-research",
        "name": "Papers and Research",
        "description": "Papers, arXiv pages, lectures, and research notes.",
        "where": "(LOWER(COALESCE(url, '') || ' ' || COALESCE(window_title, '') || ' ' || content) LIKE ? OR LOWER(COALESCE(url, '') || ' ' || COALESCE(window_title, '') || ' ' || content) LIKE ? OR LOWER(COALESCE(url, '') || ' ' || COALESCE(window_title, '') || ' ' || content) LIKE ? OR LOWER(COALESCE(url, '') || ' ' || COALESCE(window_title, '') || ' ' || content) LIKE ?)",
        "params": ["%arxiv%", "%paper%", "%lecture%", "%research%"],
    },
    {
        "id": "coding-debugging",
        "name": "Coding and Debugging",
        "description": "Code, errors, training loops, traces, and implementation work.",
        "where": "(LOWER(COALESCE(window_title, '') || ' ' || content || ' ' || COALESCE(file_path, '')) LIKE ? OR LOWER(COALESCE(window_title, '') || ' ' || content || ' ' || COALESCE(file_path, '')) LIKE ? OR LOWER(COALESCE(window_title, '') || ' ' || content || ' ' || COALESCE(file_path, '')) LIKE ? OR LOWER(COALESCE(window_title, '') || ' ' || content || ' ' || COALESCE(file_path, '')) LIKE ?)",
        "params": ["%python%", "%debug%", "%traceback%", "%train%"],
    },
    {
        "id": "notes-documents",
        "name": "Notes and Documents",
        "description": "Local documents, Notion-style notes, PDFs, and markdown files.",
        "where": "(source_type = 'file' OR LOWER(app_name || ' ' || COALESCE(window_title, '') || ' ' || COALESCE(file_path, '')) LIKE ? OR LOWER(COALESCE(file_path, '')) LIKE ? OR LOWER(COALESCE(file_path, '')) LIKE ?)",
        "params": ["%notion%", "%.pdf%", "%.md%"],
    },
    {
        "id": "career-work",
        "name": "Career and Job Search",
        "description": "Resume, internship, LinkedIn, and application-related memories.",
        "where": "(LOWER(COALESCE(url, '') || ' ' || COALESCE(window_title, '') || ' ' || content) LIKE ? OR LOWER(COALESCE(url, '') || ' ' || COALESCE(window_title, '') || ' ' || content) LIKE ? OR LOWER(COALESCE(url, '') || ' ' || COALESCE(window_title, '') || ' ' || content) LIKE ? OR LOWER(COALESCE(url, '') || ' ' || COALESCE(window_title, '') || ' ' || content) LIKE ?)",
        "params": ["%resume%", "%linkedin%", "%internship%", "%application%"],
    },
]


def smart_collections(limit_per_collection: int = 5) -> list[CollectionSummary]:
    collections: list[CollectionSummary] = []
    with connect() as conn:
        for definition in COLLECTION_DEFINITIONS:
            where = f"({definition['where']}) AND (is_noise = 0 OR is_noise IS NULL)"
            params = list(definition["params"])
            count_row = conn.execute(
                f"SELECT COUNT(*) AS count, MAX(timestamp) AS latest FROM captures WHERE {where}",
                params,
            ).fetchone()
            count = int(count_row["count"] or 0)
            if count == 0:
                continue
            rows = conn.execute(
                f"SELECT {CAPTURE_COLUMNS} FROM captures WHERE {where} ORDER BY is_pinned DESC, timestamp DESC LIMIT ?",
                [*params, limit_per_collection],
            ).fetchall()
            collections.append(
                CollectionSummary(
                    id=str(definition["id"]),
                    name=str(definition["name"]),
                    description=str(definition["description"]),
                    count=count,
                    latest_capture_at=count_row["latest"],
                    captures=[row_to_capture_result(row) for row in rows],
                )
            )
    return collections


def weekly_digest() -> dict:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)
    start_iso = start.isoformat()
    now_iso = now.isoformat()
    with connect() as conn:
        capture_count = int(conn.execute("SELECT COUNT(*) AS count FROM captures WHERE timestamp >= ?", (start_iso,)).fetchone()["count"])
        keep_count = int(conn.execute("SELECT COUNT(*) AS count FROM captures WHERE timestamp >= ? AND is_noise = 0", (start_iso,)).fetchone()["count"])
        noise_count = int(conn.execute("SELECT COUNT(*) AS count FROM captures WHERE timestamp >= ? AND is_noise = 1", (start_iso,)).fetchone()["count"])
        pinned_count = int(conn.execute("SELECT COUNT(*) AS count FROM captures WHERE timestamp >= ? AND is_pinned = 1", (start_iso,)).fetchone()["count"])
        opened_count = int(conn.execute("SELECT COUNT(*) AS count FROM search_clicks WHERE clicked_at >= ?", (start_iso,)).fetchone()["count"])
        open_todo_count = int(conn.execute("SELECT COUNT(*) AS count FROM todos WHERE status = 'open'").fetchone()["count"])
        top_apps = [dict(row) for row in conn.execute(
            """
            SELECT app_name, COUNT(*) AS count
            FROM captures
            WHERE timestamp >= ?
            GROUP BY app_name
            ORDER BY count DESC
            LIMIT 8
            """,
            (start_iso,),
        )]
        top_sources = [dict(row) for row in conn.execute(
            """
            SELECT source_type, COUNT(*) AS count
            FROM captures
            WHERE timestamp >= ?
            GROUP BY source_type
            ORDER BY count DESC
            """,
            (start_iso,),
        )]
        pinned_rows = conn.execute(
            f"SELECT {CAPTURE_COLUMNS} FROM captures WHERE is_pinned = 1 ORDER BY timestamp DESC LIMIT 8"
        ).fetchall()
        opened_rows = conn.execute(
            """
            SELECT DISTINCT
              captures.id AS id,
              captures.timestamp AS timestamp,
              captures.app_name AS app_name,
              captures.window_title AS window_title,
              captures.content AS content,
              captures.source_type AS source_type,
              captures.url AS url,
              captures.file_path AS file_path,
              captures.is_noise AS is_noise,
              captures.is_pinned AS is_pinned
            FROM captures
            JOIN search_clicks ON search_clicks.capture_id = captures.id
            WHERE search_clicks.clicked_at >= ?
            ORDER BY search_clicks.clicked_at DESC
            LIMIT 8
            """,
            (start_iso,),
        ).fetchall()
    return {
        "from_timestamp": start_iso,
        "to_timestamp": now_iso,
        "capture_count": capture_count,
        "keep_count": keep_count,
        "noise_count": noise_count,
        "pinned_count": pinned_count,
        "opened_count": opened_count,
        "open_todo_count": open_todo_count,
        "top_apps": top_apps,
        "top_sources": top_sources,
        "collections": smart_collections(limit_per_collection=3),
        "pinned_captures": [row_to_capture_result(row) for row in pinned_rows],
        "opened_captures": [row_to_capture_result(row) for row in opened_rows],
    }


def row_to_todo(row: sqlite3.Row) -> TodoItem:
    return TodoItem(
        id=int(row["id"]),
        title=str(row["title"]),
        notes=row["notes"],
        status=str(row["status"]),
        priority=int(row["priority"]),
        due_at=row["due_at"],
        source_capture_id=row["source_capture_id"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def list_todos(status: Optional[str] = None) -> list[TodoItem]:
    where = []
    params: list[object] = []
    if status:
        where.append("status = ?")
        params.append(status)
    sql = "SELECT * FROM todos"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY status ASC, priority ASC, COALESCE(due_at, '9999-12-31') ASC, created_at DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_todo(row) for row in rows]


def create_todo(
    title: str,
    notes: Optional[str],
    priority: int,
    due_at: Optional[str],
    source_capture_id: Optional[int],
) -> TodoItem:
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO todos (title, notes, priority, due_at, source_capture_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title.strip(), notes, priority, due_at, source_capture_id, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return row_to_todo(row)


def update_todo(todo_id: int, **updates) -> Optional[TodoItem]:
    allowed = ["title", "notes", "status", "priority", "due_at", "source_capture_id"]
    values = {key: value for key, value in updates.items() if key in allowed and value is not None}
    if "status" in values and values["status"] not in {"open", "done"}:
        raise ValueError("status must be open or done.")
    if not values:
        with connect() as conn:
            row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        return row_to_todo(row) if row else None
    values["updated_at"] = datetime.now(timezone.utc).isoformat()
    assignments = ", ".join(f"{key} = ?" for key in values)
    params = [*values.values(), todo_id]
    with connect() as conn:
        conn.execute(f"UPDATE todos SET {assignments} WHERE id = ?", params)
        conn.commit()
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return row_to_todo(row) if row else None


def delete_todo(todo_id: int) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
        return cursor.rowcount > 0


def _privacy_path():
    support = Path.home() / "Library" / "Application Support" / "MemoryOS"
    support.mkdir(parents=True, exist_ok=True)
    return support / "privacy.json"


DEFAULT_PRIVACY = PrivacySettings(
    blocked_apps=["1Password", "Keychain Access", "System Settings", "System Preferences"],
    blocked_domains=["bank", "chase.com", "wellsfargo.com", "capitalone.com", "paypal.com", "venmo.com"],
    excluded_path_fragments=["/Library/", "/.ssh/", "/.gnupg/", "/.Trash/"],
)


def get_privacy_settings() -> PrivacySettings:
    path = _privacy_path()
    if not path.exists():
        return DEFAULT_PRIVACY
    data = json.loads(path.read_text(encoding="utf-8"))
    return PrivacySettings(**data)


def save_privacy_settings(settings: PrivacySettings) -> PrivacySettings:
    path = _privacy_path()
    path.write_text(json.dumps(settings.dict(), indent=2), encoding="utf-8")
    return settings


def storage_stats() -> dict:
    policy = get_storage_policy()
    with connect() as conn:
        total = int(conn.execute("SELECT COUNT(*) AS count FROM captures").fetchone()["count"])
        noise = int(conn.execute("SELECT COUNT(*) AS count FROM captures WHERE is_noise = 1").fetchone()["count"])
        keep = int(conn.execute("SELECT COUNT(*) AS count FROM captures WHERE is_noise = 0").fetchone()["count"])
        oldest = conn.execute("SELECT MIN(timestamp) AS oldest FROM captures").fetchone()["oldest"]
        latest = conn.execute("SELECT MAX(timestamp) AS latest FROM captures").fetchone()["latest"]
        protected = len(_protected_capture_ids(conn, policy))

    db_size = _database_size_bytes()
    index_size = _index_size_bytes()
    log_size = _log_size_bytes()
    return {
        "database_bytes": db_size,
        "index_bytes": index_size,
        "log_bytes": log_size,
        "total_bytes": db_size + index_size + log_size,
        "total_captures": total,
        "noise_captures": noise,
        "keep_captures": keep,
        "protected_captures": protected,
        "oldest_capture_at": oldest,
        "latest_capture_at": latest,
        "policy": policy,
    }


def _delete_capture_ids(conn: sqlite3.Connection, ids: list[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    cursor = conn.execute(f"DELETE FROM captures WHERE id IN ({placeholders})", ids)
    return int(cursor.rowcount)


def _cleanup_duplicates(conn: sqlite3.Connection, protected: set[int]) -> int:
    rows = conn.execute(
        f"SELECT {CAPTURE_COLUMNS} FROM captures ORDER BY timestamp DESC, id DESC"
    ).fetchall()
    seen: set[tuple[str, str, str, str, str]] = set()
    duplicate_ids: list[int] = []
    for row in rows:
        capture_id = int(row["id"])
        key = (
            str(row["source_type"] or ""),
            str(row["app_name"] or ""),
            str(row["window_title"] or ""),
            str(row["url"] or row["file_path"] or ""),
            str(row["content"] or ""),
        )
        if key in seen and capture_id not in protected:
            duplicate_ids.append(capture_id)
        else:
            seen.add(key)
    return _delete_capture_ids(conn, duplicate_ids)


def _remove_index_artifacts() -> bool:
    removed = False
    for path in [INDEX_ARTIFACT_PATH, FAISS_INDEX_PATH, FAISS_MAPPING_PATH]:
        if path.exists():
            path.unlink()
            removed = True
    return removed


def _rotate_logs(max_bytes: int = 5_000_000) -> int:
    log_dir = PROJECT_ROOT / ".logs"
    if not log_dir.exists():
        return 0
    rotated = 0
    for path in log_dir.glob("*.log"):
        if path.stat().st_size <= max_bytes:
            continue
        rotated_path = path.with_suffix(path.suffix + ".1")
        rotated_path.unlink(missing_ok=True)
        path.rename(rotated_path)
        path.write_text("", encoding="utf-8")
        rotated += 1
    return rotated


def cleanup_storage(
    delete_noise: bool = True,
    delete_duplicates: bool = True,
    apply_retention: bool = True,
    enforce_size_cap: bool = True,
    rotate_logs: bool = True,
    rebuild_index: bool = False,
) -> CleanupResponse:
    policy = get_storage_policy()
    before_size = _database_size_bytes() + _index_size_bytes() + _log_size_bytes()
    deleted_noise = 0
    deleted_old = 0
    deleted_duplicates = 0
    deleted_for_size = 0

    with connect() as conn:
        protected = _protected_capture_ids(conn, policy)
        if delete_noise:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=policy.noise_retention_hours)).isoformat()
            cursor = conn.execute("DELETE FROM captures WHERE is_noise = 1 AND timestamp < ?", (cutoff,))
            deleted_noise = int(cursor.rowcount)

        if apply_retention:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=policy.retention_days)).isoformat()
            rows = conn.execute("SELECT id FROM captures WHERE timestamp < ? ORDER BY timestamp ASC", (cutoff,)).fetchall()
            old_ids = [int(row["id"]) for row in rows if int(row["id"]) not in protected]
            deleted_old = _delete_capture_ids(conn, old_ids)

        if delete_duplicates:
            protected = _protected_capture_ids(conn, policy)
            deleted_duplicates = _cleanup_duplicates(conn, protected)

        conn.commit()

        if enforce_size_cap and _database_size_bytes() > policy.max_database_mb * 1_000_000:
            protected = _protected_capture_ids(conn, policy)
            rows = conn.execute("SELECT id FROM captures ORDER BY timestamp ASC").fetchall()
            size_ids = []
            for row in rows:
                capture_id = int(row["id"])
                if capture_id not in protected:
                    size_ids.append(capture_id)
                if len(size_ids) >= 500:
                    break
            deleted_for_size = _delete_capture_ids(conn, size_ids)
            conn.commit()

        deleted_total = deleted_noise + deleted_old + deleted_duplicates + deleted_for_size
        if deleted_total:
            conn.execute("VACUUM")

    logs_rotated = _rotate_logs() if rotate_logs else 0
    index_removed = False
    index_rebuilt = False
    if deleted_noise + deleted_old + deleted_duplicates + deleted_for_size:
        index_removed = _remove_index_artifacts()
        if rebuild_index:
            try:
                refresh_index("auto", None, None)
                index_rebuilt = True
            except Exception:
                index_rebuilt = False

    after_size = _database_size_bytes() + _index_size_bytes() + _log_size_bytes()
    return CleanupResponse(
        deleted_noise=deleted_noise,
        deleted_old=deleted_old,
        deleted_duplicates=deleted_duplicates,
        deleted_for_size=deleted_for_size,
        logs_rotated=logs_rotated,
        index_removed=index_removed,
        index_rebuilt=index_rebuilt,
        reclaimed_hint_bytes=max(0, before_size - after_size),
    )


def export_data() -> dict:
    with connect() as conn:
        captures = [
            dict(row)
            for row in conn.execute(f"SELECT {CAPTURE_COLUMNS} FROM captures ORDER BY timestamp DESC")
        ]
        sessions = [
            dict(row)
            for row in conn.execute(
                "SELECT id, app_name, start_time, end_time, duration_s FROM sessions ORDER BY start_time DESC"
            )
        ]
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "capture_count": len(captures),
        "session_count": len(sessions),
        "captures": captures,
        "sessions": sessions,
    }


def forget_captures(
    from_timestamp: Optional[str],
    to_timestamp: Optional[str],
    app_name: Optional[str],
    source_type: Optional[str],
) -> int:
    where = []
    params = []
    if from_timestamp:
        where.append("timestamp >= ?")
        params.append(from_timestamp)
    if to_timestamp:
        where.append("timestamp <= ?")
        params.append(to_timestamp)
    if app_name:
        where.append("app_name = ?")
        params.append(app_name)
    if source_type:
        where.append("source_type = ?")
        params.append(source_type)
    if not where:
        raise ValueError("At least one delete filter is required.")

    sql = "DELETE FROM captures WHERE " + " AND ".join(where)
    with connect() as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return int(cursor.rowcount)
