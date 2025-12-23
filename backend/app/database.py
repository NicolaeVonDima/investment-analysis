"""
Database configuration and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://portfolio_user:portfolio_password@localhost:5432/portfolio_db")

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
    """Initialize database tables."""
    from app import models  # noqa: F401
    # Create all tables - SQLAlchemy will handle schema migrations
    Base.metadata.create_all(bind=engine)
    
    # Manual migration: Add tax columns if they don't exist
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        if 'scenarios' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('scenarios')]
            with engine.begin() as conn:
                if 'tax_on_sale_proceeds' not in columns:
                    try:
                        conn.execute(text('ALTER TABLE scenarios ADD COLUMN tax_on_sale_proceeds FLOAT'))
                        print("Added tax_on_sale_proceeds column to scenarios table")
                    except Exception as e:
                        print(f"Could not add tax_on_sale_proceeds column (may already exist): {e}")
                if 'tax_on_dividends' not in columns:
                    try:
                        conn.execute(text('ALTER TABLE scenarios ADD COLUMN tax_on_dividends FLOAT'))
                        print("Added tax_on_dividends column to scenarios table")
                    except Exception as e:
                        print(f"Could not add tax_on_dividends column (may already exist): {e}")
                if 'growth_cushion' not in columns:
                    try:
                        conn.execute(text('ALTER TABLE scenarios ADD COLUMN growth_cushion FLOAT DEFAULT 0.02'))
                        print("Added growth_cushion column to scenarios table")
                    except Exception as e:
                        print(f"Could not add growth_cushion column (may already exist): {e}")
    except Exception as e:
        print(f"Warning: Could not migrate database schema: {e}")
    
    print("Database tables initialized successfully")

