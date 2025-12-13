"""
Database configuration and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL")
# Dev fallback when running without Docker/Postgres.
# In Docker, DATABASE_URL is always provided via compose env.
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./dev.db"

if DATABASE_URL.startswith("sqlite:"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    # Import models so SQLAlchemy registers all tables on Base.metadata
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Ensure critical constraints/indexes exist even if tables already existed.
    # NOTE: SQLAlchemy `create_all` will not add constraints to pre-existing tables.
    try:
        with engine.begin() as conn:
            # Enforce "at most one snapshot per ticker per day" globally.
            # If duplicates already exist, this index creation may fail; we keep the app running.
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_data_snapshots_ticker_snapshot_date "
                    "ON data_snapshots (ticker, snapshot_date)"
                )
            )
    except Exception:
        # Best-effort; do not prevent app startup due to index creation.
        pass

