"""
Database connection layer for HA-Autopilot.
Supports SQLite and MariaDB/MySQL backends with automatic fallback.

Implementation Notes:
- MariaDB is checked first but only used if it contains 'states' table
- SQLite is used as reliable fallback
- Connection pooling configured for MariaDB
- Read-only mode enforced for SQLite to prevent accidental writes
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

    Architecture:
    1. Try MariaDB connection
    2. If MariaDB accessible, check for 'states' table
    3. If table exists, use MariaDB; otherwise fall back to SQLite
    4. If MariaDB fails, use SQLite

    Args:
        db_url: SQLAlchemy connection string. If None, auto-detects database.
        query_timeout: Maximum seconds per query (default 30).

    Example:
        db = DatabaseConnector()  # Auto-detect
        db = DatabaseConnector(db_url="sqlite:////path/to/db")  # Explicit
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

        Detection Logic:
        1. Try MariaDB at configured host
        2. If connection succeeds, check for 'states' table
        3. If table exists, return MariaDB URL
        4. Otherwise, fall back to SQLite

        Phase 2 Note:
        This method can be extended to check multiple MariaDB databases
        or different hosts for distributed setups.

        Returns:
            SQLAlchemy connection URL string
        """
        # Try MariaDB first
        # SANITIZED: Replace with actual credentials in production
        mariadb_url = "mysql+pymysql://DB_USER:DB_PASSWORD@DB_HOST/DB_NAME?charset=utf8mb4"

        try:
            test_engine = create_engine(mariadb_url, pool_pre_ping=True)
            with test_engine.connect() as conn:
                # Check if MariaDB has Home Assistant tables
                # Critical: Don't just check connectivity, verify data exists
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

        Sets read-only mode for SQLite to prevent accidental writes.
        MariaDB connections use the configured user's permissions.

        Usage:
            with db.get_connection() as conn:
                result = conn.execute(text("SELECT * FROM states LIMIT 10"))
        """
        conn = self.engine.connect()
        try:
            if self.is_sqlite:
                # Prevent accidental writes to HA database
                conn.execute(text("PRAGMA query_only = ON"))
            yield conn
        finally:
            conn.close()

    def test_connection(self) -> dict:
        """
        Verify database connectivity and return basic statistics.

        Returns:
            Dictionary with database metadata:
            - total_states: Total state records
            - entity_count: Unique entities
            - earliest_timestamp: First record timestamp
            - latest_timestamp: Last record timestamp
            - database_type: "SQLite" or "MariaDB"

        Phase 2 Integration:
            This method provides baseline metrics. Phase 2 can extend this
            to include pattern-specific statistics (e.g., most active entities,
            time range coverage, data quality metrics).
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
