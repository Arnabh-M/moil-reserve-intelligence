"""FastAPI application factory for the OreSight API."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from neo4j.exceptions import ServiceUnavailable
from sqlalchemy import text
from sqlalchemy.exc import InterfaceError, OperationalError

from app.config import get_settings
from app.db import engine
from app.graph_db import close_graph_driver, graph_health, init_graph_driver
from app.routers import (
    admin,
    demo,
    equipment,
    kpi,
    production,
    recommendations,
    reports,
    reserve_zones,
    risk_events,
    simulate,
    site_notes,
    sites,
)
from app.services.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger("oresight")
logging.basicConfig(level=logging.INFO)

settings = get_settings()

_ERROR_CODES_BY_STATUS = {
    400: "BAD_REQUEST",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _error_code_for_status(status_code: int) -> str:
    return _ERROR_CODES_BY_STATUS.get(status_code, "ERROR")


def mask_db_url(url: str) -> str:
    """Return `url` with any password component replaced by `***`."""
    parts = urlsplit(url)
    if parts.password is None:
        return url

    userinfo = parts.username or ""
    userinfo += ":***"
    netloc = f"{userinfo}@{parts.hostname or ''}"
    if parts.port:
        netloc += f":{parts.port}"

    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def check_database() -> bool:
    """Attempt a lightweight connection to Postgres. Never raises."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - health check must never raise
        logger.warning("Database health check failed", exc_info=True)
        return False


def check_neo4j() -> bool:
    """Lightweight Neo4j connectivity check via the shared driver. Never raises."""
    return graph_health()["status"] == "connected"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("OreSight API starting (env=%s)", settings.APP_ENV)
    logger.info("Database URL: %s", mask_db_url(settings.DATABASE_URL))
    logger.info("Neo4j URI: %s", settings.NEO4J_URI)
    init_graph_driver()
    start_scheduler()
    yield
    stop_scheduler()
    close_graph_driver()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title="OreSight API",
        version="0.1.0",
        description=(
            "Backend API for OreSight - a mine reserve intelligence prototype "
            "built for SIH26009 (MOIL manganese mining)."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": _error_code_for_status(exc.status_code),
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": jsonable_encoder(exc.errors()),
                "error_code": "VALIDATION_ERROR",
            },
        )

    @app.exception_handler(OperationalError)
    @app.exception_handler(InterfaceError)
    async def handle_db_unavailable(request: Request, exc: Exception) -> JSONResponse:
        """Postgres unreachable / connection dropped mid-request. This is a
        transient infra condition, not a bug — 503, not 500, and no traceback.
        """
        logger.warning(
            "Database unavailable processing %s %s: %s",
            request.method, request.url.path, exc.__class__.__name__,
        )
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Database is temporarily unavailable. Please retry shortly.",
                "error_code": "SERVICE_UNAVAILABLE",
            },
        )

    @app.exception_handler(ServiceUnavailable)
    async def handle_graph_unavailable(request: Request, exc: Exception) -> JSONResponse:
        """Neo4j unreachable. Endpoints that can degrade (causal-graph,
        reports) handle it themselves and never reach here; this covers the
        ones that genuinely need the graph (recommendations, simulate).
        """
        logger.warning(
            "Graph service unavailable processing %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Graph service (Neo4j) is temporarily unavailable. Please retry shortly.",
                "error_code": "SERVICE_UNAVAILABLE",
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception processing %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"},
        )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        db_ok = check_database()
        neo4j_ok = check_neo4j()
        return {
            "status": "ok",
            "service": "oresight-api",
            "db": "connected" if db_ok else "unavailable",
            "neo4j": "connected" if neo4j_ok else "unavailable",
        }

    app.include_router(sites.router)
    app.include_router(equipment.router)
    app.include_router(production.router)
    app.include_router(risk_events.router)
    app.include_router(reserve_zones.router)
    app.include_router(recommendations.router)
    app.include_router(reports.router)
    app.include_router(simulate.router)
    app.include_router(kpi.router)
    app.include_router(site_notes.router)
    app.include_router(demo.router)
    app.include_router(admin.router)

    return app


app = create_app()
