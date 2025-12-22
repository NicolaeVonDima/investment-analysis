"""
Database configuration and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./portfolio_data.db")

# Ensure data directory exists for SQLite
if DATABASE_URL.startswith("sqlite:"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if db_path != ":memory:":
        db_dir = Path(db_path).parent
        if db_dir and str(db_dir) != ".":
            db_dir.mkdir(parents=True, exist_ok=True)
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
    from app import models  # noqa: F401
    # Create all tables - this will add new columns if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # For SQLite, we need to manually add new columns if they don't exist
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        if 'portfolios' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('portfolios')]
            with engine.begin() as conn:  # Use begin() for transaction
                if 'risk_label' not in columns:
                    try:
                        conn.execute(text('ALTER TABLE portfolios ADD COLUMN risk_label VARCHAR'))
                        print("Added risk_label column to portfolios table")
                    except Exception as e:
                        print(f"Could not add risk_label column (may already exist): {e}")
                if 'overperform_strategy' not in columns:
                    try:
                        conn.execute(text('ALTER TABLE portfolios ADD COLUMN overperform_strategy TEXT'))
                        print("Added overperform_strategy column to portfolios table")
                    except Exception as e:
                        print(f"Could not add overperform_strategy column (may already exist): {e}")
                if 'strategy' not in columns:
                    try:
                        conn.execute(text('ALTER TABLE portfolios ADD COLUMN strategy TEXT'))
                        print("Added strategy column to portfolios table")
                    except Exception as e:
                        print(f"Could not add strategy column (may already exist): {e}")
    except Exception as e:
        print(f"Warning: Could not migrate database schema: {e}")

