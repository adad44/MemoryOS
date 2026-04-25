from __future__ import annotations

import logging
import time

from abstraction_engine import run_abstraction


log = logging.getLogger("scheduler")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def safe_run() -> None:
    try:
        log.info("Starting abstraction run")
        run_abstraction()
        log.info("Abstraction run complete")
    except Exception as exc:
        log.error("Abstraction run failed: %s", exc)


if __name__ == "__main__":
    log.info("Scheduler started - running abstraction every 6 hours")
    safe_run()
    while True:
        time.sleep(6 * 60 * 60)
        safe_run()
