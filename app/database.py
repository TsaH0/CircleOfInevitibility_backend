"""
Database configuration and session management.
Supports both SQLite (local development) and PostgreSQL (Neon production).
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load environment variables from .env file
load_dotenv()

# Database URL - defaults to SQLite if DATABASE_URL not set
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mastercp.db")

# Configure engine based on database type
if "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
    # PostgreSQL (Neon) configuration
    # Neon requires SSL for connections
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,  # Connection pool size
        max_overflow=10,  # Max connections beyond pool_size
        pool_recycle=300,  # Recycle connections after 5 minutes
        connect_args={
            "sslmode": "require",  # Neon requires SSL
        },
    )
elif "sqlite" in DATABASE_URL:
    # SQLite configuration (local development)
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Required for SQLite with FastAPI
    )
else:
    # Generic fallback
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_database_type() -> str:
    """Return a description of the current database type."""
    if "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
        return "PostgreSQL (Neon)"
    elif "sqlite" in DATABASE_URL:
        return "SQLite (local)"
    else:
        return "Unknown"


def init_db():
    """Initialize database tables."""
    from . import models  # Import models to register them

    db_type = get_database_type()
    print(f"Connecting to database: {db_type}")

    # Test connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connection successful!")
    except Exception as e:
        print(f"Warning: Could not verify database connection: {e}")
        raise

    Base.metadata.create_all(bind=engine)
    print(f"Database tables initialized ({db_type})")
