"""Alembic environment configuration.

The connection URL always comes from app.config.get_settings().DATABASE_URL
(which in turn reads DATABASE_URL from the environment / .env). The
`sqlalchemy.url` key in alembic.ini is intentionally left blank.
"""

from logging.config import fileConfig

from alembic import context
from geoalchemy2.alembic_helpers import include_object, render_item, writer
from sqlalchemy import engine_from_config, pool, text

# Make sure "app" is importable when alembic is run from the project root.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings  # noqa: E402
from app.db import Base  # noqa: E402

# Import model modules here so Base.metadata is fully populated for autogenerate.
import app.models  # noqa: E402,F401

# this is the Alembic Config object, which provides access to values
# within the .ini file in use.
config = context.config

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (with a live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # The postgis/postgis image sets the database search_path to
        # "public, topology, tiger" so the tiger-geocoder/topology extension
        # functions work unqualified. Reflection with schema=None (what
        # Alembic uses for autogenerate) walks the *entire* search_path, so
        # without pinning it to "public" here, autogenerate sees dozens of
        # tiger/topology tables as "removed" and tries to drop them.
        connection.execute(text("SET search_path TO public"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=False,
            include_object=include_object,
            render_item=render_item,
            process_revision_directives=writer,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
