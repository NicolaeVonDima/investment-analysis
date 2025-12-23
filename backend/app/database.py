"""
Database configuration and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Require DATABASE_URL to be set - no local fallback
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable must be set")

# Create engine with connection pooling for PostgreSQL
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=5,  # Number of connections to maintain
    max_overflow=10  # Additional connections that can be created on demand
)

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
    """Initialize database tables using SQLAlchemy models.
    
    All tables are defined in models.py and will be created automatically.
    For schema changes, use proper database migrations (e.g., Alembic).
    """
    from app import models  # noqa: F401 - Import models to register them with Base
    # Create all tables - SQLAlchemy will handle table creation
    # This is idempotent - existing tables won't be recreated
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized successfully")

