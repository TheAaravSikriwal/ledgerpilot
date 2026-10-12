"""Background sync loop. Re-reads the interval setting every tick so changes apply at once."""

import asyncio
import logging
import time

from fastapi import FastAPI

from .settings_store import get_setting

log = logging.getLogger(__name__)

TICK_SECONDS = 5


async def run_scheduler(app: FastAPI) -> None:
    last = time.monotonic()
    while True:
        await asyncio.sleep(TICK_SECONDS)
        try:
            with app.state.session_factory() as session:
                interval = int(get_setting(session, "sync_interval_minutes"))
            if time.monotonic() - last >= interval * 60:
                await asyncio.to_thread(app.state.sync_engine.run, "schedule")
                last = time.monotonic()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("scheduled sync failed")
            last = time.monotonic()
