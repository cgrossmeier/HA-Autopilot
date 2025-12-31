"""
Database connection layer for HA-Autopilot.
Supports SQLite and MariaDB/MySQL backends with automatic fallback.
Change MariaDB Database Connection String in Line 62  mariadb_url = "mysql+pymysql://[user]:[password]@[serverip]/ha_autopilot?charset=utf8mb4"
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class DatabaseConnector:
    """
    Read-only database connection manager.

    Args:
        db_url: SQLAlchemy connection string. If None, tries MariaDB then auto-detects SQLite.
        query_timeout: Maximum seconds per query (default 30).
    """

    def __init__(self, db_url: str = None, query_timeout: int = 30):
        if db_url is None:
            # Try MariaDB first, then fall back to SQLite
            db_url = self._auto_detect_database()

        self.db_url = db_url
        self.query_timeout = query_timeout
        self.is_sqlite = db_url.startswith("sqlite")

        # Connection pool settings
        pool_kwargs = {
            "pool_pre_ping": True,  # Verify connections before use
            "pool_recycle": 3600,   # Recycle connections after 1 hour
        }

        if not self.is_sqlite:
            pool_kwargs["poolclass"] = QueuePool
            pool_kwargs["pool_size"] = 2
            pool_kwargs["max_overflow"] = 3

        try:
            self.engine = create_engine(
                db_url,
                echo=False,
                **pool_kwargs
            )
            logger.info(f"Database connector initialized: {'SQLite' if self.is_sqlite else 'MariaDB/MySQL'}")
        except Exception as e:
            logger.error(f"Failed to create database engine: {e}")
            raise

    def _auto_detect_database(self) -> str:
        """
        Auto-detect database connection.
        Tries MariaDB first (if it has HA data), then falls back to SQLite.
        """
        # Try MariaDB first
        mariadb_url = "mysql+pymysql://[user]:[password]@[serverip]/ha_autopilot?charset=utf8mb4"
        try:
            test_engine = create_engine(mariadb_url, pool_pre_ping=True)
            with test_engine.connect() as conn:
                # Check if MariaDB has Home Assistant tables
                result = conn.execute(text("SHOW TABLES LIKE 'states'"))
                if result.fetchone():
                    logger.info("MariaDB database detected with Home Assistant data")
                    return mariadb_url
                else:
                    logger.info("MariaDB accessible but empty, falling back to SQLite")
        except Exception as e:
            logger.warning(f"MariaDB connection failed, falling back to SQLite: {e}")

        # Fall back to SQLite
        db_path = "/config/home-assistant_v2.db"
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found at {db_path} and MariaDB is unavailable")

        logger.info("Using SQLite database")
        return f"sqlite:///{db_path}"

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        Sets read-only mode for SQLite.
        """
        conn = self.engine.connect()
        try:
            if self.is_sqlite:
                # Prevent accidental writes
                conn.execute(text("PRAGMA query_only = ON"))
            yield conn
        finally:
            conn.close()

    def test_connection(self) -> dict:
        """
        Verify database connectivity and return basic stats.
        """
        with self.get_connection() as conn:
            # Count total states
            result = conn.execute(text("SELECT COUNT(*) FROM states"))
            state_count = result.scalar()

            # Count unique entities
            result = conn.execute(text("SELECT COUNT(*) FROM states_meta"))
            entity_count = result.scalar()

            # Get date range
            result = conn.execute(text("""
                SELECT MIN(last_updated_ts), MAX(last_updated_ts)
                FROM states
                WHERE last_updated_ts IS NOT NULL
            """))
            row = result.fetchone()

            return {
                "total_states": state_count,
                "entity_count": entity_count,
                "earliest_timestamp": row[0],
                "latest_timestamp": row[1],
                "database_type": "SQLite" if self.is_sqlite else "MariaDB"
            }
