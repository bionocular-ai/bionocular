"""Database setup for extraction system.

This module provides minimal database setup for the extractor system.
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .database_models import Base

logger = logging.getLogger(__name__)


class DatabaseSetup:
    """Simple database setup for extraction system."""

    def __init__(self, database_url: str = "sqlite:///extraction.db"):
        """Initialize database setup.

        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None

    def setup_database(self):
        """Setup database tables."""
        try:
            # Create engine
            self.engine = create_engine(self.database_url, echo=False)

            # Create tables
            Base.metadata.create_all(bind=self.engine)

            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=self.engine
            )

            logger.info("Database setup complete")

        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            raise

    def get_session(self):
        """Get database session."""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized. Call setup_database() first.")
        return self.SessionLocal()
