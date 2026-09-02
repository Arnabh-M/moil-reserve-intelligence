"""SQLAlchemy engine, session factory, declarative base, and FastAPI dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
    # Fail fast when Postgres is unreachable instead of hanging the request
    # for the OS-default TCP timeout — a hung page demos worse than a clean
    # 503 (see app.main's OperationalError handler).
    connect_args={"connect_timeout": 3},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models (GeoAlchemy2-aware)."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
