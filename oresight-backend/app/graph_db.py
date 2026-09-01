"""Neo4j driver lifecycle + health check for the causal-graph layer.

One process-wide `neo4j.Driver` (the driver is a thread-safe connection
pool — the docs are explicit that you create exactly one per application
and share it). It is created lazily on first use, reused for every request
and every scheduler run, and closed once on app shutdown via the FastAPI
lifespan in `app.main`.

Connection details come from `app.config.get_settings()` (NEO4J_URI /
NEO4J_USER / NEO4J_PASSWORD, loaded from `.env`) — never hardcoded here.

Usage:
    from fastapi import Depends
    from neo4j import Driver
    from app.graph_db import get_graph_driver

    @router.get(...)
    def endpoint(driver: Driver = Depends(get_graph_driver)):
        with driver.session() as session:
            ...
"""

from __future__ import annotations

import logging

from neo4j import Driver, GraphDatabase

from app.config import get_settings

logger = logging.getLogger("oresight.graph")

_driver: Driver | None = None


def init_graph_driver() -> Driver:
    """Return the shared Neo4j driver, creating it on first call.

    Safe to call repeatedly (idempotent) and from any thread — used both by
    the FastAPI lifespan on startup and by the background scheduler.
    """
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_lifetime=3600,
            max_connection_pool_size=20,
            connection_acquisition_timeout=30,
        )
        logger.info("Neo4j driver initialised for %s", settings.NEO4J_URI)
    return _driver


def get_graph_driver() -> Driver:
    """FastAPI dependency: hand the shared driver to a request.

    The driver is a long-lived pool, so there is nothing to open or close
    per-request — endpoint code opens a short `with driver.session()` block
    itself. Kept as a dependency (rather than a bare import) so tests can
    override it with a fake driver.
    """
    return init_graph_driver()


def close_graph_driver() -> None:
    """Close the shared driver if it was ever created. Safe to call twice."""
    global _driver
    if _driver is not None:
        try:
            _driver.close()
            logger.info("Neo4j driver closed")
        except Exception:  # noqa: BLE001 - shutdown must never raise
            logger.warning("Error closing Neo4j driver", exc_info=True)
        finally:
            _driver = None


def graph_health() -> dict[str, str]:
    """Lightweight connectivity probe. Never raises.

    Returns `{"status": "connected"}` or
    `{"status": "unavailable", "detail": "<reason>"}`.
    """
    try:
        driver = init_graph_driver()
        driver.verify_connectivity()
        return {"status": "connected"}
    except Exception as exc:  # noqa: BLE001 - health check must never raise
        logger.warning("Neo4j health check failed", exc_info=True)
        return {"status": "unavailable", "detail": str(exc)}
