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
            dialect = engine.dialect.name

            # Enforce "at most one snapshot per ticker per day" globally.
            # If duplicates already exist, this index creation may fail; we keep the app running.
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_data_snapshots_ticker_snapshot_date "
                    "ON data_snapshots (ticker, snapshot_date)"
                )
            )

            # Best-effort schema upgrades for existing databases.
            # NOTE: SQLAlchemy create_all won't ALTER existing tables.
            #
            # Keep local dev (SQLite) and Docker (Postgres) robust without manual migrations for now.
            if dialect == "postgresql":
                # provider_symbol_map.last_verified_at
                conn.execute(
                    text(
                        "ALTER TABLE provider_symbol_map "
                        "ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMPTZ NULL"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_provider_symbol_map_last_verified_at "
                        "ON provider_symbol_map (last_verified_at)"
                    )
                )

                # provider_symbol_search_cache table (24h symbol search cache)
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS provider_symbol_search_cache ("
                        "id SERIAL PRIMARY KEY, "
                        "provider VARCHAR(64) NOT NULL DEFAULT 'alpha_vantage', "
                        "query VARCHAR(64) NOT NULL, "
                        "fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
                        "payload JSONB NOT NULL"
                        ")"
                    )
                )
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ux_provider_symbol_search_cache_provider_query "
                        "ON provider_symbol_search_cache (provider, query)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_provider_symbol_search_cache_provider_fetched "
                        "ON provider_symbol_search_cache (provider, fetched_at)"
                    )
                )

                # instrument_refresh table (browse-lite 24h cache state)
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS instrument_refresh ("
                        "instrument_id INTEGER PRIMARY KEY REFERENCES instruments(id) ON DELETE CASCADE, "
                        "last_refresh_at TIMESTAMPTZ NULL, "
                        "last_status VARCHAR(32) NULL, "
                        "last_error TEXT NULL, "
                        "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
                        "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                        ")"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_instrument_refresh_last_refresh_at "
                        "ON instrument_refresh (last_refresh_at)"
                    )
                )
            elif dialect == "sqlite":
                # SQLite supports ADD COLUMN but not IF NOT EXISTS; run best-effort.
                try:
                    conn.execute(text("ALTER TABLE provider_symbol_map ADD COLUMN last_verified_at DATETIME NULL"))
                except Exception:
                    pass
                try:
                    conn.execute(
                        text("CREATE INDEX IF NOT EXISTS ix_provider_symbol_map_last_verified_at ON provider_symbol_map (last_verified_at)")
                    )
                except Exception:
                    pass
    except Exception:
        # Best-effort; do not prevent app startup due to index creation.
        pass

