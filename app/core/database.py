# ==============================================================================
# Database Configuration and Session Management
# ==============================================================================
# This module handles all database-related configuration using SQLModel.
# SQLModel is a library that combines SQLAlchemy and Pydantic, providing
# both ORM functionality and data validation in a single model definition.
#
# Key Components:
#   - engine: The SQLAlchemy engine for database connections
#   - get_session: Dependency injection function for FastAPI routes
#   - create_db_and_tables: Initialize database schema
#
# Supabase + pgvector:
#   - Supabase provides PostgreSQL with pgvector extension
#   - pgvector enables efficient vector similarity search
#   - Use for ML embedding storage and retrieval
# ==============================================================================

from sqlmodel import SQLModel, Session, create_engine
from typing import Generator
import logging

from app.core.config import settings

# Configure logging for database operations
logger = logging.getLogger(__name__)

# ==============================================================================
# DATABASE ENGINE
# ==============================================================================
# The engine is the starting point for SQLAlchemy - it maintains a pool
# of connections to the database.
#
# Configuration options:
#   - echo: Log all SQL statements (useful for debugging)
#   - pool_pre_ping: Test connections before using them
#   - pool_size: Number of connections to keep open
#   - max_overflow: Additional connections allowed beyond pool_size
# ==============================================================================

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,  # Set to True to see SQL queries in logs
    # Connection pool settings (adjust based on your Supabase plan)
    pool_pre_ping=True,  # Verify connection is alive before using
    # pool_size=5,       # Uncomment to limit connection pool size
    # max_overflow=10,   # Uncomment to limit overflow connections
)


def create_db_and_tables() -> None:
    """
    Create all database tables defined by SQLModel models.
    
    This function should be called on application startup to ensure
    all tables exist. SQLModel will only create tables that don't exist;
    it won't modify existing tables (use Alembic for migrations).
    
    IMPORTANT: Import all models before calling this function!
    Models must be imported so SQLModel.metadata knows about them.
    
    Usage:
        @app.on_event("startup")
        def on_startup():
            create_db_and_tables()
    
    Note on pgvector:
        Before using vector columns, ensure pgvector extension is enabled:
        SQL: CREATE EXTENSION IF NOT EXISTS vector;
        This is typically done once in Supabase SQL Editor.
    """
    # Import all models to register them with SQLModel.metadata
    # This import is here to avoid circular imports
    from app.models import User  # noqa: F401
    # Add more model imports as you create them:
    # from app.models import Product, Category, etc.
    
    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created successfully!")


def get_session() -> Generator[Session, None, None]:
    """
    Dependency injection function for database sessions.
    
    Use this with FastAPI's Depends() to get a database session
    in your route handlers. The session is automatically closed
    after the request completes.
    
    Usage in routes:
        from fastapi import Depends
        from sqlmodel import Session
        from app.core.database import get_session
        
        @router.get("/items")
        def get_items(session: Session = Depends(get_session)):
            items = session.exec(select(Item)).all()
            return items
    
    The session provides:
        - session.exec(): Execute SELECT queries
        - session.add(): Add new objects
        - session.delete(): Delete objects
        - session.commit(): Commit transaction
        - session.refresh(): Refresh object from DB
    """
    with Session(engine) as session:
        logger.debug("Database session opened")
        try:
            yield session
        finally:
            logger.debug("Database session closed")


# ==============================================================================
# HELPER FUNCTIONS FOR COMMON DATABASE OPERATIONS
# ==============================================================================

def get_engine():
    """
    Get the database engine instance.
    
    Useful for advanced operations like:
        - Running raw SQL
        - Database introspection
        - Creating custom connection contexts
    """
    return engine


# ==============================================================================
# PGVECTOR SETUP INSTRUCTIONS
# ==============================================================================
# To enable pgvector in your Supabase database:
#
# 1. Go to Supabase Dashboard > SQL Editor
# 2. Run: CREATE EXTENSION IF NOT EXISTS vector;
# 3. Verify: SELECT * FROM pg_extension WHERE extname = 'vector';
#
# After enabling pgvector, you can use Vector columns in your models.
# See app/models/item.py for an example of vector column usage.
#
# For similarity search queries, use pgvector operators:
#   - <->  : L2 (Euclidean) distance
#   - <#>  : Inner product (negative)
#   - <=>  : Cosine distance
#
# Example similarity search (in a service):
#   from sqlalchemy import text
#   query = text('''
#       SELECT id, name, embedding <-> :query_vector AS distance
#       FROM items
#       ORDER BY distance
#       LIMIT :limit
#   ''')
#   result = session.execute(query, {"query_vector": str(vector), "limit": 10})
# ==============================================================================
