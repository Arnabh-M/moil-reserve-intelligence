"""Regression tests for Alembic migration correctness.

These reproduce, automatically and against disposable databases, the two
failure modes hit while building the Twin State migration:

1. Autogenerate seeing tiger-geocoder/topology tables - pulled in because the
   postgis/postgis Docker image sets a database-wide search_path spanning
   `public, topology, tiger` - and wanting to drop them. This can only be
   triggered by `alembic revision --autogenerate` (the diff/comparison path);
   plain `upgrade`/`downgrade` never run it, so it needs its own test with
   those extensions actually installed on a throwaway DB.
2. `alembic upgrade head` silently doing nothing (exit 0, zero tables)
   because a `SET search_path` statement auto-began a transaction that
   Alembic's own transaction manager then deferred to instead of committing.
   Plain upgrade/downgrade already exercises this.

Never touches the dev `oresight` database - everything runs against
disposable `oresight_test*` databases on the same Postgres server, created
and dropped by these tests. Skips (not fails) if Postgres isn't reachable.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_TABLES = {
    "sites",
    "reserve_zones",
    "equipment",
    "production_records",
    "risk_events",
}
EXPECTED_ENUM_TYPES = {"equipment_status", "risk_severity"}


def _maintenance_url(dev_url: str) -> str:
    """URL to Postgres's own `postgres` maintenance DB, for CREATE/DROP DATABASE."""
    return make_url(dev_url).set(database="postgres").render_as_string(hide_password=False)


def _postgres_reachable(maintenance_url: str) -> bool:
    try:
        engine = create_engine(maintenance_url, connect_args={"connect_timeout": 3})
        with engine.connect():
            pass
        engine.dispose()
        return True
    except SQLAlchemyError:
        return False


def _drop_database(admin_engine, name: str) -> None:
    with admin_engine.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": name},
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))


def _create_database(admin_engine, name: str) -> None:
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))


def _install_tiger_and_topology(db_url: str) -> None:
    """Reproduce the real dev DB's condition: tiger-geocoder + topology
    extensions installed, with search_path spanning all three schemas at the
    database level - exactly how the postgis/postgis image configures
    `oresight`. This is what actually caused bug #1, so the regression test
    for it must recreate this condition rather than run on a bare database.
    """
    engine = create_engine(db_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_topology"))
            conn.execute(
                text("CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder CASCADE")
            )
            db_name = make_url(db_url).database
            conn.execute(
                text(f'ALTER DATABASE "{db_name}" SET search_path TO public, topology, tiger')
            )
    finally:
        engine.dispose()


def _table_names(db_url: str, schema: str = "public") -> set[str]:
    engine = create_engine(db_url)
    try:
        return set(inspect(engine).get_table_names(schema=schema))
    finally:
        engine.dispose()


def _enum_type_names(db_url: str) -> set[str]:
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT DISTINCT t.typname FROM pg_type t "
                    "JOIN pg_enum e ON t.oid = e.enumtypid"
                )
            ).all()
        return {row[0] for row in rows}
    finally:
        engine.dispose()


def _non_public_tables(db_url: str) -> set[tuple[str, str]]:
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT table_schema, table_name FROM information_schema.tables "
                    "WHERE table_schema NOT IN ('public', 'information_schema', 'pg_catalog') "
                    "AND table_type = 'BASE TABLE'"
                )
            ).all()
        return {(row[0], row[1]) for row in rows}
    finally:
        engine.dispose()


def _alembic_config() -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    return cfg


@pytest.fixture
def _admin_engine():
    dev_url = get_settings().DATABASE_URL
    maintenance_url = _maintenance_url(dev_url)

    if not _postgres_reachable(maintenance_url):
        pytest.skip("Postgres is not reachable (is `docker compose up -d` running?)")

    engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    yield engine
    engine.dispose()


@pytest.fixture
def plain_test_db_url(_admin_engine, monkeypatch):
    """A bare throwaway database - no postgis/tiger/topology preinstalled.
    The migration's own `CREATE EXTENSION IF NOT EXISTS postgis;` must set
    up everything it needs from scratch.
    """
    name = "oresight_test"
    dev_url = get_settings().DATABASE_URL
    db_url = make_url(dev_url).set(database=name).render_as_string(hide_password=False)

    _drop_database(_admin_engine, name)
    _create_database(_admin_engine, name)

    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    try:
        yield db_url
    finally:
        get_settings.cache_clear()
        _drop_database(_admin_engine, name)


@pytest.fixture
def polluted_test_db_url(_admin_engine, monkeypatch):
    """A throwaway database pre-polluted with tiger-geocoder + topology,
    replicating the real dev DB's search_path exactly - the condition that
    actually causes bug #1.
    """
    name = "oresight_test_tiger"
    dev_url = get_settings().DATABASE_URL
    db_url = make_url(dev_url).set(database=name).render_as_string(hide_password=False)

    _drop_database(_admin_engine, name)
    _create_database(_admin_engine, name)
    _install_tiger_and_topology(db_url)

    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    try:
        yield db_url
    finally:
        get_settings.cache_clear()
        _drop_database(_admin_engine, name)


def test_migration_upgrade_downgrade_cycle_is_clean(plain_test_db_url):
    """Regression test for bug #2 (silent no-op migration): upgrade head must
    actually create tables, downgrade base must actually drop them (tables
    AND enum types - the specific thing that breaks if DROP TYPE is missing
    or misordered), and a repeat upgrade must succeed.
    """
    cfg = _alembic_config()

    # 1 + 2. upgrade head against the clean throwaway DB
    command.upgrade(cfg, "head")

    # 3. all 5 expected tables exist
    tables = _table_names(plain_test_db_url)
    assert EXPECTED_TABLES <= tables, f"missing tables after upgrade: {EXPECTED_TABLES - tables}"

    # 4. nothing was created outside the public schema
    leaked = _non_public_tables(plain_test_db_url)
    assert leaked == set(), f"migration created tables outside 'public': {leaked}"

    # 5. downgrade base drops all 5 tables AND both native enum types
    command.downgrade(cfg, "base")

    tables_after_downgrade = _table_names(plain_test_db_url)
    assert not (EXPECTED_TABLES & tables_after_downgrade), (
        f"tables still present after downgrade: {EXPECTED_TABLES & tables_after_downgrade}"
    )

    enums_after_downgrade = _enum_type_names(plain_test_db_url)
    assert not (EXPECTED_ENUM_TYPES & enums_after_downgrade), (
        f"enum types still present after downgrade: {EXPECTED_ENUM_TYPES & enums_after_downgrade}"
    )

    # 6. upgrade head a second time must succeed cleanly - proves downgrade
    # actually cleaned up enough for a repeat upgrade, not just once
    command.upgrade(cfg, "head")

    tables_final = _table_names(plain_test_db_url)
    assert EXPECTED_TABLES <= tables_final, (
        f"second upgrade after downgrade failed to recreate: {EXPECTED_TABLES - tables_final}"
    )


def test_autogenerate_ignores_tiger_and_topology_schemas(polluted_test_db_url):
    """Regression test for bug #1: with tiger-geocoder + topology installed
    and the database's search_path spanning public/topology/tiger (exactly
    how the postgis/postgis Docker image configures the real dev database),
    autogenerate must produce an empty diff when no models changed. If the
    search_path pin (or include_schemas=False) in env.py is ever reverted,
    this fails with a generated migration full of DROP TABLE statements for
    tiger/topology tables.
    """
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    script = command.revision(cfg, message="regression_test_probe", autogenerate=True)
    assert script is not None and script.path is not None
    generated_path = Path(script.path)

    try:
        source = generated_path.read_text()
        upgrade_body = source.split("def upgrade() -> None:", 1)[1].split(
            "def downgrade() -> None:", 1
        )[0]
        downgrade_body = source.split("def downgrade() -> None:", 1)[1]

        assert "op." not in upgrade_body, (
            "autogenerate detected spurious upgrade operations with no model "
            f"changes - tiger/topology leakage regression:\n{upgrade_body}"
        )
        assert "op." not in downgrade_body, (
            "autogenerate detected spurious downgrade operations with no model "
            f"changes - tiger/topology leakage regression:\n{downgrade_body}"
        )
    finally:
        generated_path.unlink(missing_ok=True)
