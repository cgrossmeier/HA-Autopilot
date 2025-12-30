"""
Pattern storage layer for HA Autopilot.

Handles all database operations for pattern persistence.
Supports both SQLite and MariaDB via Phase 1's database connector.
"""

import sys
sys.path.insert(0, '/config/ha_autopilot')

import json
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

from sqlalchemy import text, create_engine
from sqlalchemy.exc import IntegrityError

from database import DatabaseConnector
from .const import (
    TABLE_PATTERNS,
    TABLE_TRANSACTIONS,
    TABLE_SEQUENCES,
    TABLE_METADATA,
    STATUS_ACTIVE,
    FEEDBACK_APPROVED,
    FEEDBACK_REJECTED,
)

_LOGGER = logging.getLogger(__name__)


# ============================================================================
# SQL Query Templates
# ============================================================================

class QueryTemplates:
    """Centralized SQL query templates."""
    
    @staticmethod
    def create_patterns_table(is_sqlite: bool) -> str:
        autoincrement = "AUTOINCREMENT" if is_sqlite else "AUTO_INCREMENT"
        boolean_type = "BOOLEAN" if is_sqlite else "TINYINT(1)"
        
        return f"""
            CREATE TABLE IF NOT EXISTS {TABLE_PATTERNS} (
                pattern_id INTEGER PRIMARY KEY {autoincrement},
                pattern_type TEXT NOT NULL,
                pattern_hash TEXT UNIQUE,
                trigger_conditions TEXT NOT NULL,
                action_target TEXT NOT NULL,
                confidence REAL NOT NULL,
                support REAL NOT NULL,
                lift REAL,
                conviction REAL,
                pattern_score REAL NOT NULL,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                occurrence_count INTEGER NOT NULL,
                user_feedback TEXT,
                automation_id TEXT,
                suggestion_shown {boolean_type} DEFAULT 0,
                status TEXT DEFAULT '{STATUS_ACTIVE}',
                deprecated_by INTEGER,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """
    
    @staticmethod
    def create_transactions_table(is_sqlite: bool) -> str:
        autoincrement = "AUTOINCREMENT" if is_sqlite else "AUTO_INCREMENT"
        
        return f"""
            CREATE TABLE IF NOT EXISTS {TABLE_TRANSACTIONS} (
                transaction_id INTEGER PRIMARY KEY {autoincrement},
                window_start REAL NOT NULL,
                window_end REAL NOT NULL,
                context_day_type TEXT,
                context_time_bucket TEXT,
                items TEXT NOT NULL,
                quality_score REAL,
                created_at REAL NOT NULL
            )
        """
    
    @staticmethod
    def create_sequences_table(is_sqlite: bool) -> str:
        autoincrement = "AUTOINCREMENT" if is_sqlite else "AUTO_INCREMENT"
        
        return f"""
            CREATE TABLE IF NOT EXISTS {TABLE_SEQUENCES} (
                sequence_id INTEGER PRIMARY KEY {autoincrement},
                pattern_id INTEGER NOT NULL,
                step_order INTEGER NOT NULL,
                entity_id TEXT NOT NULL,
                state TEXT NOT NULL,
                typical_delay_seconds INTEGER
            )
        """
    
    @staticmethod
    def create_metadata_table() -> str:
        return f"""
            CREATE TABLE IF NOT EXISTS {TABLE_METADATA} (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at REAL NOT NULL
            )
        """


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class PatternRow:
    """Represents a pattern database row with named fields."""
    pattern_id: int
    pattern_type: str
    pattern_hash: str
    trigger_conditions: Dict
    action_target: Dict
    confidence: float
    support: float
    lift: Optional[float]
    conviction: Optional[float]
    pattern_score: float
    first_seen: float
    last_seen: float
    occurrence_count: int
    user_feedback: Optional[str]
    automation_id: Optional[str]
    suggestion_shown: bool
    status: str
    deprecated_by: Optional[int]
    created_at: float
    updated_at: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "pattern_hash": self.pattern_hash,
            "trigger_conditions": self.trigger_conditions,
            "action_target": self.action_target,
            "confidence": self.confidence,
            "support": self.support,
            "lift": self.lift,
            "conviction": self.conviction,
            "pattern_score": self.pattern_score,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "occurrence_count": self.occurrence_count,
            "user_feedback": self.user_feedback,
            "automation_id": self.automation_id,
            "suggestion_shown": self.suggestion_shown,
            "status": self.status,
            "deprecated_by": self.deprecated_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ============================================================================
# Main Storage Class
# ============================================================================

class PatternStorage:
    """
    Database storage for discovered patterns.
    
    Uses the same database as Home Assistant's recorder,
    but with separate tables for pattern data.
    
    Thread Safety:
        This class is designed to be called from executor threads.
        All methods are synchronous and use database connections safely.
    """
    
    def __init__(self, hass):
        """
        Initialize pattern storage.
        
        Args:
            hass: Home Assistant instance (for accessing recorder DB)
        """
        self.hass = hass
        self.db = DatabaseConnector()
        _LOGGER.info(f"Pattern storage using {self.db.db_url}")
    
    # ========================================================================
    # Schema Management
    # ========================================================================
    
    def initialize_schema(self):
        """
        Create pattern storage tables if they don't exist.
        
        Idempotent: Safe to call multiple times.
        Uses IF NOT EXISTS for all table creation.
        """
        with self.db.get_connection() as conn:
            conn.execute(text(QueryTemplates.create_patterns_table(self.db.is_sqlite)))
            conn.execute(text(QueryTemplates.create_transactions_table(self.db.is_sqlite)))
            conn.execute(text(QueryTemplates.create_sequences_table(self.db.is_sqlite)))
            conn.execute(text(QueryTemplates.create_metadata_table()))
            
            self._create_indexes(conn)
            conn.commit()
            
        _LOGGER.info("Pattern storage schema initialized")
    
    def _create_indexes(self, conn):
        """Create indexes for query performance."""
        indexes = [
            f"CREATE INDEX IF NOT EXISTS idx_patterns_type ON {TABLE_PATTERNS}(pattern_type)",
            f"CREATE INDEX IF NOT EXISTS idx_patterns_score ON {TABLE_PATTERNS}(pattern_score DESC)",
            f"CREATE INDEX IF NOT EXISTS idx_patterns_feedback ON {TABLE_PATTERNS}(user_feedback)",
            f"CREATE INDEX IF NOT EXISTS idx_patterns_status ON {TABLE_PATTERNS}(status)",
            f"CREATE INDEX IF NOT EXISTS idx_transactions_window ON {TABLE_TRANSACTIONS}(window_start, window_end)",
            f"CREATE INDEX IF NOT EXISTS idx_sequences_pattern ON {TABLE_SEQUENCES}(pattern_id)",
        ]
        
        for idx in indexes:
            try:
                conn.execute(text(idx))
            except Exception as e:
                _LOGGER.debug(f"Index creation note: {e}")
    
    # ========================================================================
    # Pattern Operations
    # ========================================================================
    
    def store_pattern(self, pattern: Dict) -> Optional[int]:
        """
        Store a discovered pattern.
        
        Handles deduplication via pattern_hash.
        If pattern already exists, updates occurrence_count and metrics.
        
        Args:
            pattern: Pattern dictionary with required fields
            
        Returns:
            pattern_id if stored/updated, None on error
        """
        pattern_hash = self._calculate_pattern_hash(
            pattern["trigger_conditions"],
            pattern["action_target"]
        )
        now = datetime.now().timestamp()
        
        with self.db.get_connection() as conn:
            existing = self._get_existing_pattern(conn, pattern_hash)
            
            if existing:
                return self._update_existing_pattern(conn, existing, pattern, now)
            else:
                return self._insert_new_pattern(conn, pattern, pattern_hash, now)
    
    def _get_existing_pattern(self, conn, pattern_hash: str) -> Optional[tuple]:
        """Check if pattern already exists."""
        result = conn.execute(
            text(f"SELECT pattern_id, occurrence_count FROM {TABLE_PATTERNS} WHERE pattern_hash = :hash"),
            {"hash": pattern_hash}
        )
        return result.fetchone()
    
    def _update_existing_pattern(self, conn, existing: tuple, pattern: Dict, now: float) -> int:
        """Update metrics for existing pattern."""
        pattern_id, old_count = existing
        new_count = old_count + pattern.get("occurrence_count", 1)
        
        conn.execute(text(f"""
            UPDATE {TABLE_PATTERNS}
            SET confidence = :confidence,
                support = :support,
                lift = :lift,
                conviction = :conviction,
                pattern_score = :score,
                last_seen = :last_seen,
                occurrence_count = :count,
                updated_at = :updated_at
            WHERE pattern_id = :id
        """), {
            "confidence": pattern["confidence"],
            "support": pattern["support"],
            "lift": pattern.get("lift"),
            "conviction": pattern.get("conviction"),
            "score": pattern["pattern_score"],
            "last_seen": now,
            "count": new_count,
            "updated_at": now,
            "id": pattern_id
        })
        conn.commit()
        
        _LOGGER.debug(f"Updated existing pattern {pattern_id}")
        return pattern_id
    
    def _insert_new_pattern(self, conn, pattern: Dict, pattern_hash: str, now: float) -> int:
        """Insert a new pattern."""
        result = conn.execute(text(f"""
            INSERT INTO {TABLE_PATTERNS} (
                pattern_type, pattern_hash, trigger_conditions,
                action_target, confidence, support, lift, conviction,
                pattern_score, first_seen, last_seen, occurrence_count,
                created_at, updated_at
            ) VALUES (
                :type, :hash, :triggers, :action, :confidence,
                :support, :lift, :conviction, :score, :first_seen,
                :last_seen, :count, :created_at, :updated_at
            )
        """), {
            "type": pattern["pattern_type"],
            "hash": pattern_hash,
            "triggers": json.dumps(pattern["trigger_conditions"]),
            "action": json.dumps(pattern["action_target"]),
            "confidence": pattern["confidence"],
            "support": pattern["support"],
            "lift": pattern.get("lift"),
            "conviction": pattern.get("conviction"),
            "score": pattern["pattern_score"],
            "first_seen": now,
            "last_seen": now,
            "count": pattern.get("occurrence_count", 1),
            "created_at": now,
            "updated_at": now
        })
        conn.commit()
        
        pattern_id = result.lastrowid
        _LOGGER.info(f"Stored new pattern {pattern_id} (score: {pattern['pattern_score']:.2f})")
        return pattern_id
    
    def get_patterns(
        self,
        min_score: float = 0.0,
        pattern_type: str = None,
        status: str = STATUS_ACTIVE,
        feedback: str = None,
        limit: int = None
    ) -> List[Dict]:
        """
        Retrieve patterns with filters.
        
        Args:
            min_score: Minimum pattern score
            pattern_type: Filter by type ('association', 'sequence', etc.)
            status: Pattern status filter
            feedback: User feedback filter
            limit: Maximum results
            
        Returns:
            List of pattern dictionaries
        """
        query, params = self._build_pattern_query(
            min_score, pattern_type, status, feedback, limit
        )
        
        with self.db.get_connection() as conn:
            result = conn.execute(text(query), params)
            return [self._row_to_pattern_dict(row) for row in result]
    
    def _build_pattern_query(
        self,
        min_score: float,
        pattern_type: Optional[str],
        status: Optional[str],
        feedback: Optional[str],
        limit: Optional[int]
    ) -> tuple[str, Dict]:
        """Build dynamic query based on filters."""
        query = f"SELECT * FROM {TABLE_PATTERNS} WHERE pattern_score >= :min_score"
        params = {"min_score": min_score}
        
        if pattern_type:
            query += " AND pattern_type = :type"
            params["type"] = pattern_type
        
        if status:
            query += " AND status = :status"
            params["status"] = status
        
        if feedback:
            query += " AND user_feedback = :feedback"
            params["feedback"] = feedback
        
        query += " ORDER BY pattern_score DESC"
        
        if limit:
            query += " LIMIT :limit"
            params["limit"] = limit
        
        return query, params
    
    def _row_to_pattern_dict(self, row) -> Dict:
        """Convert database row to pattern dictionary."""
        return {
            "pattern_id": row[0],
            "pattern_type": row[1],
            "pattern_hash": row[2],
            "trigger_conditions": json.loads(row[3]),
            "action_target": json.loads(row[4]),
            "confidence": row[5],
            "support": row[6],
            "lift": row[7],
            "conviction": row[8],
            "pattern_score": row[9],
            "first_seen": row[10],
            "last_seen": row[11],
            "occurrence_count": row[12],
            "user_feedback": row[13],
            "automation_id": row[14],
            "suggestion_shown": row[15],
            "status": row[16],
            "deprecated_by": row[17],
            "created_at": row[18],
            "updated_at": row[19],
        }
    
    def update_pattern_feedback(self, pattern_id: int, feedback: str):
        """
        Record user feedback on a pattern.
        
        Args:
            pattern_id: Pattern to update
            feedback: 'approved', 'rejected', or 'ignored'
        """
        with self.db.get_connection() as conn:
            conn.execute(text(f"""
                UPDATE {TABLE_PATTERNS}
                SET user_feedback = :feedback,
                    updated_at = :updated_at
                WHERE pattern_id = :id
            """), {
                "feedback": feedback,
                "updated_at": datetime.now().timestamp(),
                "id": pattern_id
            })
            conn.commit()
            
        _LOGGER.info(f"Updated pattern {pattern_id} feedback: {feedback}")
    
    def mark_pattern_suggested(self, pattern_id: int):
        """Mark that a pattern suggestion has been shown to user."""
        with self.db.get_connection() as conn:
            conn.execute(text(f"""
                UPDATE {TABLE_PATTERNS}
                SET suggestion_shown = 1,
                    updated_at = :updated_at
                WHERE pattern_id = :id
            """), {
                "updated_at": datetime.now().timestamp(),
                "id": pattern_id
            })
            conn.commit()
    
    # ========================================================================
    # Transaction Operations
    # ========================================================================
    
    def store_transaction(self, transaction: Dict) -> int:
        """
        Store a transaction for pattern mining.
        
        Transactions are used as input for association rule learning.
        
        Returns:
            transaction_id
        """
        now = datetime.now().timestamp()
        
        with self.db.get_connection() as conn:
            result = conn.execute(text(f"""
                INSERT INTO {TABLE_TRANSACTIONS} (
                    window_start, window_end, context_day_type,
                    context_time_bucket, items, quality_score, created_at
                ) VALUES (
                    :start, :end, :day_type, :time_bucket,
                    :items, :quality, :created_at
                )
            """), {
                "start": transaction["window_start"],
                "end": transaction["window_end"],
                "day_type": transaction.get("context_day_type"),
                "time_bucket": transaction.get("context_time_bucket"),
                "items": json.dumps(transaction["items"]),
                "quality": transaction.get("quality_score"),
                "created_at": now
            })
            conn.commit()
            
        return result.lastrowid
    
    def get_transactions(
        self,
        start_time: float = None,
        end_time: float = None,
        context_filter: Dict = None
    ) -> List[Dict]:
        """
        Retrieve transactions for analysis.
        
        Args:
            start_time: Filter transactions after this timestamp
            end_time: Filter transactions before this timestamp
            context_filter: Dict with day_type and/or time_bucket
            
        Returns:
            List of transaction dictionaries
        """
        query, params = self._build_transaction_query(
            start_time, end_time, context_filter
        )
        
        with self.db.get_connection() as conn:
            result = conn.execute(text(query), params)
            return [self._row_to_transaction_dict(row) for row in result]
    
    def _build_transaction_query(
        self,
        start_time: Optional[float],
        end_time: Optional[float],
        context_filter: Optional[Dict]
    ) -> tuple[str, Dict]:
        """Build dynamic transaction query."""
        query = f"SELECT * FROM {TABLE_TRANSACTIONS} WHERE 1=1"
        params = {}
        
        if start_time:
            query += " AND window_start >= :start"
            params["start"] = start_time
        
        if end_time:
            query += " AND window_end <= :end"
            params["end"] = end_time
        
        if context_filter:
            if "day_type" in context_filter:
                query += " AND context_day_type = :day_type"
                params["day_type"] = context_filter["day_type"]
            
            if "time_bucket" in context_filter:
                query += " AND context_time_bucket = :time_bucket"
                params["time_bucket"] = context_filter["time_bucket"]
        
        query += " ORDER BY window_start"
        return query, params
    
    def _row_to_transaction_dict(self, row) -> Dict:
        """Convert database row to transaction dictionary."""
        return {
            "transaction_id": row[0],
            "window_start": row[1],
            "window_end": row[2],
            "context_day_type": row[3],
            "context_time_bucket": row[4],
            "items": json.loads(row[5]),
            "quality_score": row[6],
            "created_at": row[7],
        }
    
    # ========================================================================
    # Statistics and Utilities
    # ========================================================================
    
    def get_statistics(self) -> Dict:
        """Get pattern database statistics."""
        with self.db.get_connection() as conn:
            stats = {
                "by_type_status": {},
                "total_patterns": 0,
                "total_transactions": 0,
            }
            
            # Count patterns by type and status
            result = conn.execute(text(f"""
                SELECT pattern_type, status, COUNT(*), AVG(pattern_score)
                FROM {TABLE_PATTERNS}
                GROUP BY pattern_type, status
            """))
            
            for row in result:
                key = f"{row[0]}_{row[1]}"
                stats["by_type_status"][key] = {
                    "count": row[2],
                    "avg_score": round(row[3], 3) if row[3] else 0
                }
                stats["total_patterns"] += row[2]
            
            # Count transactions
            result = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_TRANSACTIONS}"))
            stats["total_transactions"] = result.scalar()
            
        return stats
    
    def clear_all_patterns(self):
        """Clear all pattern data. Use with caution."""
        with self.db.get_connection() as conn:
            conn.execute(text(f"DELETE FROM {TABLE_SEQUENCES}"))
            conn.execute(text(f"DELETE FROM {TABLE_PATTERNS}"))
            conn.execute(text(f"DELETE FROM {TABLE_TRANSACTIONS}"))
            conn.commit()
            
        _LOGGER.warning("All pattern data cleared")
    
    # ========================================================================
    # Hash Utilities
    # ========================================================================
    
    def _calculate_pattern_hash(self, triggers, action) -> str:
        """
        Calculate a deterministic hash for pattern deduplication.
        
        The hash is based on the structure of triggers and action,
        not on the exact JSON representation (which might vary).
        """
        # Sort triggers for consistent hashing
        trigger_sig = json.dumps(sorted(json.dumps(triggers)), sort_keys=True)
        action_sig = json.dumps(action, sort_keys=True)
        combined = f"{trigger_sig}|{action_sig}"
        
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
