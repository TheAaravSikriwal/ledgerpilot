from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from ledgerpilot import models  # noqa: F401  (registers tables on Base.metadata)
from ledgerpilot.config import get_config
from ledgerpilot.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:  # programmatic upgrade from the app
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(get_config().db_url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
