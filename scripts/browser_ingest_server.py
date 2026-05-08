#!/usr/bin/env python3
import json
import os
import platform
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


if platform.system() == "Darwin":
    DEFAULT_DATA_DIR = os.path.expanduser("~/Library/Application Support/MemoryOS")
else:
    DEFAULT_DATA_DIR = os.path.join(
        os.path.expanduser(os.environ.get("XDG_DATA_HOME", "~/.local/share")),
        "memoryos",
    )

DB_PATH = os.environ.get("MEMORYOS_DB", os.path.join(DEFAULT_DATA_DIR, "memoryos.db"))


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
  embedding    BLOB
);

CREATE TABLE IF NOT EXISTS sessions (
  id          INTEGER PRIMARY KEY,
  app_name    TEXT NOT NULL,
  start_time  DATETIME NOT NULL,
  end_time    DATETIME,
  duration_s  INTEGER
);
"""


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)


def iso_timestamp(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/capture/browser":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
            content = " ".join(str(payload["content"]).split())
            if len(content) < 20:
                raise ValueError("content too short")
        except Exception as exc:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(exc).encode())
            return

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO captures
                (timestamp, app_name, window_title, content, source_type, url, file_path)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    iso_timestamp(payload.get("timestamp")),
                    "Browser",
                    payload.get("title"),
                    content[:3000],
                    "browser",
                    payload.get("url"),
                ),
            )

        self.send_response(204)
        self.end_headers()

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print(f"MemoryOS browser ingest listening on http://127.0.0.1:8765")
    print(f"Database: {DB_PATH}")
    server.serve_forever()
