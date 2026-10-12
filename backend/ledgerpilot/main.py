"""App factory. Run with:  uvicorn ledgerpilot.main:create_app --factory --host 127.0.0.1"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import date

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, func, select

from . import __version__
from .api import routes_business, routes_data, routes_system
from .categorize.ai import AICategorizer
from .config import BACKEND_DIR, AppConfig, get_config
from .db import make_engine, make_session_factory
from .demo import mock_source_factory, reset_demo
from .events import EventBus
from .models import Account, MockState
from .scheduler import run_scheduler
from .seed import seed_reference_data
from .sync import SyncEngine

log = logging.getLogger("ledgerpilot")


def migrate(engine: Engine) -> None:
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")


def create_app(config: AppConfig | None = None, today: Callable[[], date] = date.today) -> FastAPI:
    config = config or get_config()
    engine = make_engine(config.db_url)
    session_factory = make_session_factory(engine)
    bus = EventBus()
    ai = AICategorizer(config.anthropic_api_key) if config.ai_available else None
    sync_engine = SyncEngine(session_factory, mock_source_factory(today), bus, ai)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        bus.attach(asyncio.get_running_loop())
        await asyncio.to_thread(migrate, engine)
        with session_factory() as session:
            seed_reference_data(session)
            first_run = session.get(MockState, 1) is None and not session.scalar(
                select(func.count(Account.id))
            )
        if first_run:
            log.info("first run: installing the demo household")
            await asyncio.to_thread(
                reset_demo, session_factory, config.ledgerpilot_mock_seed, today()
            )
            await asyncio.to_thread(sync_engine.run, "reset")
        task = asyncio.create_task(run_scheduler(app)) if config.ledgerpilot_scheduler else None
        yield
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        engine.dispose()

    app = FastAPI(title="LedgerPilot", version=__version__, lifespan=lifespan)
    app.state.config = config
    app.state.session_factory = session_factory
    app.state.bus = bus
    app.state.sync_engine = sync_engine
    app.state.today = today
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (routes_data, routes_business, routes_system):
        app.include_router(module.router, prefix="/api")
    return app
