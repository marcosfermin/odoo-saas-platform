"""
Database connection and session management
Provides database utilities for the Odoo SaaS Platform
"""

import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://odoo:odoo@localhost:5432/odoo_saas')

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,   # Recycle connections after 1 hour
    echo=False,          # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Thread-safe session
Session = scoped_session(SessionLocal)


@contextmanager
def get_db_session():
    """
    Provide a transactional scope around a series of operations.

    Usage:
        with get_db_session() as session:
            user = session.query(User).first()
            session.commit()

    Yields:
        Session: SQLAlchemy database session
    """
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()


def get_db():
    """
    Get a database session (for dependency injection in FastAPI/Flask)

    Usage:
        db = get_db()
        try:
            # Do database operations
            db.commit()
        except:
            db.rollback()
            raise
        finally:
            db.close()

    Returns:
        Session: SQLAlchemy database session
    """
    db = Session()
    try:
        return db
    finally:
        pass  # Don't close here - let the caller handle it


def init_db():
    """
    Initialize the database schema
    Creates all tables defined in models
    """
    from shared.models import Base
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully")


def drop_db():
    """
    Drop all database tables (use with caution!)
    """
    from shared.models import Base
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("All database tables dropped")


def check_db_connection():
    """
    Check if database connection is working

    Returns:
        bool: True if connection is successful
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


# Event listeners for connection management
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Handle new database connections"""
    logger.debug("New database connection established")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Handle connection checkout from pool"""
    logger.debug("Database connection checked out from pool")
