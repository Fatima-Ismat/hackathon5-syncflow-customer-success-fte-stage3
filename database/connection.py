"""
database/connection.py
SyncFlow Customer Success Digital FTE — Stage 3

Database connection management.

Environment:
  DATABASE_URL=postgresql://user:pass@host:5432/syncflow_crm   (production)
  DATABASE_URL=sqlite:///./syncflow_dev.db                     (local dev fallback)

If DATABASE_URL is not set, defaults to SQLite in-memory for testing.
"""

import os
import logging
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

logger = logging.getLogger("syncflow.database")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./syncflow_dev.db"  # Safe local default
)

# Normalize Heroku/Railway-style postgres:// → postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_MEMORY = DATABASE_URL == "sqlite://"

logger.info("Database mode: %s", "PostgreSQL" if not IS_SQLITE else "SQLite")


# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────

def _make_engine():
    if IS_MEMORY:
        return create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
    elif IS_SQLITE:
        return create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    else:
        return create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            echo=False,
        )


engine = _make_engine()

# Enable WAL mode for SQLite (better concurrency)
if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(conn, record):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ─────────────────────────────────────────────────────────────────────────────
# Dependency (FastAPI)
# ─────────────────────────────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Init
# ─────────────────────────────────────────────────────────────────────────────

def init_db():
    """
    Create all tables if they don't exist.
    In production, use Alembic migrations instead.
    """
    from database.models import Base  # noqa: avoid circular at module level
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error("Failed to initialize database tables: %s", e)
        raise


def check_connection() -> bool:
    """Return True if the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database connection check failed: %s", e)
        return False
