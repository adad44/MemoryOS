from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ML_ROOT = PROJECT_ROOT / "ml"
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from memoryos.config import database_path
from memoryos.db import connect


def run_migrations() -> None:
    with connect() as conn:
        tables = [
            row["name"]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name IN ('beliefs', 'user_model', 'abstraction_runs')
                ORDER BY name
                """
            )
        ]
    print(f"Phase 7 schema applied to {database_path()}")
    print("Tables:", ", ".join(tables))


if __name__ == "__main__":
    run_migrations()
