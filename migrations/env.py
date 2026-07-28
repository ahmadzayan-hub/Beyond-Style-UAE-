"""Alembic environment: migrations against the SQLModel domain schema.

`sqlalchemy.url` in alembic.ini points at var/bsos.db relative to the repo
root; override with BSOS_DB_URL for other locations.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

import bsos.memory.domain  # noqa: F401 — imports register every table on the metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if os.environ.get("BSOS_DB_URL"):
    config.set_main_option("sqlalchemy.url", os.environ["BSOS_DB_URL"])

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite: ALTER via batch mode
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
