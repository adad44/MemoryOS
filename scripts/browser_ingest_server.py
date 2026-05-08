#!/usr/bin/env python3
import json
import os
import platform
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ML_ROOT = ROOT / "ml"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from backend.service import insert_browser_capture
from memoryos.db import connect


if platform.system() == "Darwin":
    DEFAULT_DATA_DIR = os.path.expanduser("~/Library/Application Support/MemoryOS")
else:
    DEFAULT_DATA_DIR = os.path.join(
        os.path.expanduser(os.environ.get("XDG_DATA_HOME", "~/.local/share")),
        "memoryos",
    )

DB_PATH = os.environ.get("MEMORYOS_DB", os.path.join(DEFAULT_DATA_DIR, "memoryos.db"))


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with connect(Path(DB_PATH)):
        pass


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

        insert_browser_capture(
            url=payload.get("url"),
            title=payload.get("title"),
            content=content,
            timestamp=payload.get("timestamp"),
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
