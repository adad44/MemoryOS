from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .config import database_path


SCHEMA = """
CREATE TABLE IF NOT EXISTS captures (
  id           INTEGER PRIMARY KEY,
  timestamp    DATETIME NOT NULL,
  app_name     TEXT NOT NULL,
  window_title TEXT,
  content      TEXT NOT NULL,
  source_type  TEXT NOT NULL,
  url          TEXT,
  file_path    TEXT,
  is_noise     INTEGER DEFAULT NULL,
  is_pinned    INTEGER NOT NULL DEFAULT 0,
  embedding    BLOB
);

CREATE TABLE IF NOT EXISTS sessions (
  id          INTEGER PRIMARY KEY,
  app_name    TEXT NOT NULL,
  start_time  DATETIME NOT NULL,
  end_time    DATETIME,
  duration_s  INTEGER
);

CREATE TABLE IF NOT EXISTS search_clicks (
  id          INTEGER PRIMARY KEY,
  query       TEXT NOT NULL,
  capture_id  INTEGER NOT NULL,
  rank        INTEGER,
  dwell_ms    INTEGER,
  clicked_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(capture_id) REFERENCES captures(id)
);

CREATE TABLE IF NOT EXISTS todos (
  id          INTEGER PRIMARY KEY,
  title       TEXT NOT NULL,
  notes       TEXT,
  status      TEXT NOT NULL DEFAULT 'open',
  priority    INTEGER NOT NULL DEFAULT 2,
  due_at      DATETIME,
  source_capture_id INTEGER,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(source_capture_id) REFERENCES captures(id)
);

CREATE TABLE IF NOT EXISTS beliefs (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  topic             TEXT NOT NULL,
  belief_type       TEXT NOT NULL CHECK(belief_type IN ('interest', 'knowledge', 'gap', 'pattern', 'project')),
  summary           TEXT NOT NULL,
  confidence        REAL NOT NULL DEFAULT 0.5 CHECK(confidence BETWEEN 0 AND 1),
  depth             TEXT CHECK(depth IN ('surface', 'familiar', 'intermediate', 'deep')),
  evidence          TEXT,
  first_seen        DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_updated      DATETIME DEFAULT CURRENT_TIMESTAMP,
  times_reinforced  INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_model (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  generated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  summary         TEXT NOT NULL,
  top_interests   TEXT NOT NULL,
  active_projects TEXT,
  work_rhythm     TEXT,
  knowledge_gaps  TEXT,
  raw_json        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS abstraction_runs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  finished_at     DATETIME,
  captures_read   INTEGER DEFAULT 0,
  beliefs_written INTEGER DEFAULT 0,
  beliefs_updated INTEGER DEFAULT 0,
  status          TEXT DEFAULT 'running' CHECK(status IN ('running', 'complete', 'failed')),
  error           TEXT
);

CREATE INDEX IF NOT EXISTS idx_captures_timestamp ON captures(timestamp);
CREATE INDEX IF NOT EXISTS idx_captures_app ON captures(app_name);
CREATE INDEX IF NOT EXISTS idx_captures_noise ON captures(is_noise);
CREATE INDEX IF NOT EXISTS idx_search_clicks_capture ON search_clicks(capture_id);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_beliefs_topic ON beliefs(topic);
CREATE INDEX IF NOT EXISTS idx_beliefs_type ON beliefs(belief_type);
CREATE INDEX IF NOT EXISTS idx_beliefs_confidence ON beliefs(confidence DESC);
"""


CAPTURE_COLUMNS = """
id, timestamp, app_name, window_title, content, source_type, url, file_path, is_noise, is_pinned
"""


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    db_path = Path(path or database_path())
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    click_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(search_clicks)").fetchall()
    }
    if "dwell_ms" not in click_columns:
        conn.execute("ALTER TABLE search_clicks ADD COLUMN dwell_ms INTEGER")
        conn.commit()
    capture_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(captures)").fetchall()
    }
    if "is_pinned" not in capture_columns:
        conn.execute("ALTER TABLE captures ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    conn.execute("CREATE INDEX IF NOT EXISTS idx_captures_pinned ON captures(is_pinned)")
    conn.commit()


def capture_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS count FROM captures").fetchone()
    return int(row["count"])


def fetch_captures(
    conn: sqlite3.Connection,
    limit: Optional[int] = None,
    labeled: Optional[bool] = None,
    non_noise: bool = False,
) -> List[sqlite3.Row]:
    where = []
    params: List[object] = []
    if labeled is True:
        where.append("is_noise IS NOT NULL")
    elif labeled is False:
        where.append("is_noise IS NULL")
    if non_noise:
        where.append("(is_noise = 0 OR is_noise IS NULL)")

    sql = f"SELECT {CAPTURE_COLUMNS} FROM captures"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY timestamp DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return list(conn.execute(sql, params))


def fetch_captures_by_ids(conn: sqlite3.Connection, ids: Sequence[int]) -> List[sqlite3.Row]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT {CAPTURE_COLUMNS} FROM captures WHERE id IN ({placeholders})",
        list(ids),
    ).fetchall()
    by_id = {int(row["id"]): row for row in rows}
    return [by_id[capture_id] for capture_id in ids if capture_id in by_id]


def update_noise_labels(conn: sqlite3.Connection, labels: Iterable[tuple[int, int]]) -> int:
    values = [(int(label), int(capture_id)) for capture_id, label in labels]
    conn.executemany("UPDATE captures SET is_noise = ? WHERE id = ?", values)
    conn.commit()
    return len(values)


def update_embeddings(conn: sqlite3.Connection, values: Iterable[tuple[int, bytes]]) -> int:
    rows = [(blob, int(capture_id)) for capture_id, blob in values]
    conn.executemany("UPDATE captures SET embedding = ? WHERE id = ?", rows)
    conn.commit()
    return len(rows)
