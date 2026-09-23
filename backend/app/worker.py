"""Background worker (B2.5): `python -m app.worker` runs the jobs in
`app/services/jobs.py` every `JOBS_INTERVAL_SECONDS`; `--once` runs a single pass and
exits (a cron-style trigger or a manual run). SIGTERM / SIGINT stop it between passes.
It runs no DDL — the backend's startup does.
"""

import argparse
import asyncio
import logging
import signal

from app.config import settings
from app.services.jobs import run_all
from app.services.notifications import drain

log = logging.getLogger("app.worker")


async def main(once: bool) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    log.info("worker: started (every %ss)", settings.jobs_interval_seconds)
    while True:
        results = await run_all()
        await drain()  # let the outbox sends started by this pass finish
        log.info("worker: pass done %s", results)
        if once or stop.is_set():
            break
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.jobs_interval_seconds)
            break
        except TimeoutError:
            continue
    log.info("worker: stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="run one pass and exit")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(main(parser.parse_args().once))
