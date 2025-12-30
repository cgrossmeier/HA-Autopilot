“”“

Pattern storage layer for HA Autopilot.

Handles all database operations for pattern persistence.

Supports both SQLite and MariaDB via Phase 1’s database connector.

“”“

import sys

sys.path.insert(0, ‘/config/ha_autopilot’)

import json

import hashlib

from datetime import datetime

from typing import List, Dict, Optional

import logging

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

class PatternStorage:

“”“

Database storage for discovered patterns.

Uses the same database as Home Assistant’s recorder,

but with separate tables for pattern data.

Thread Safety:

This class is designed to be called from executor threads.

All methods are synchronous and use database connections safely.

“”“

def __init__(self, hass):

“”“

Initialize pattern storage.

Args:

hass: Home Assistant instance (for accessing recorder DB)

“”“

self.hass = hass

# Use Phase 1’s database connector for smart fallback

self.db = DatabaseConnector()

_LOGGER.info(f”Pattern storage using {self.db.db_url}”)

def initialize_schema(self):

“”“

Create pattern storage tables if they don’t exist.

Idempotent: Safe to call multiple times.

Uses IF NOT EXISTS for all table creation.

“”“

with self.db.get_connection() as conn:

# Main pattern table

conn.execute(text(f”“”

CREATE TABLE IF NOT EXISTS {TABLE_PATTERNS} (

pattern_id INTEGER PRIMARY KEY {”AUTOINCREMENT” if self.db.is_sqlite else “AUTO_INCREMENT”},

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

suggestion_shown {”BOOLEAN” if self.db.is_sqlite else “TINYINT(1)”} DEFAULT 0,

status TEXT DEFAULT ‘{STATUS_ACTIVE}’,

deprecated_by INTEGER,

created_at REAL NOT NULL,

updated_at REAL NOT NULL

)

“”“))

# Transaction table

conn.execute(text(f”“”

CREATE TABLE IF NOT EXISTS {TABLE_TRANSACTIONS} (

transaction_id INTEGER PRIMARY KEY {”AUTOINCREMENT” if self.db.is_sqlite else “AUTO_INCREMENT”},

window_start REAL NOT NULL,

window_end REAL NOT NULL,

context_day_type TEXT,

context_time_bucket TEXT,

items TEXT NOT NULL,

quality_score REAL,

created_at REAL NOT NULL

)

“”“))

# Sequence steps table

conn.execute(text(f”“”

CREATE TABLE IF NOT EXISTS {TABLE_SEQUENCES} (

sequence_id INTEGER PRIMARY KEY {”AUTOINCREMENT” if self.db.is_sqlite else “AUTO_INCREMENT”},

pattern_id INTEGER NOT NULL,

step_order INTEGER NOT NULL,

entity_id TEXT NOT NULL,

state TEXT NOT NULL,

typical_delay_seconds INTEGER

)

“”“))

# Metadata table

conn.execute(text(f”“”

CREATE TABLE IF NOT EXISTS {TABLE_METADATA} (

key TEXT PRIMARY KEY,

value TEXT,

updated_at REAL NOT NULL

)

“”“))

# Create indexes

self._create_indexes(conn)

conn.commit()

_LOGGER.info(”Pattern storage schema initialized”)

def _create_indexes(self, conn):

“”“Create indexes for query performance.”“”

indexes = [

f”CREATE INDEX IF NOT EXISTS idx_patterns_type ON {TABLE_PATTERNS}(pattern_type)”,

f”CREATE INDEX IF NOT EXISTS idx_patterns_score ON {TABLE_PATTERNS}(pattern_score DESC)”,

f”CREATE INDEX IF NOT EXISTS idx_patterns_feedback ON {TABLE_PATTERNS}(user_feedback)”,

f”CREATE INDEX IF NOT EXISTS idx_patterns_status ON {TABLE_PATTERNS}(status)”,

f”CREATE INDEX IF NOT EXISTS idx_transactions_window ON {TABLE_TRANSACTIONS}(window_start, window_end)”,

f”CREATE INDEX IF NOT EXISTS idx_sequences_pattern ON {TABLE_SEQUENCES}(pattern_id)”,

]

for idx in indexes:

try:

conn.execute(text(idx))

except Exception as e:

# Index might already exist, that’s fine

_LOGGER.debug(f”Index creation note: {e}”)

def store_pattern(self, pattern: Dict) -> Optional[int]:

“”“

Store a discovered pattern.

Handles deduplication via pattern_hash.

If pattern already exists, updates occurrence_count and metrics.

Args:

pattern: Pattern dictionary with required fields

Returns:

pattern_id if stored/updated, None on error

“”“

# Calculate pattern hash for deduplication

pattern_hash = self._calculate_pattern_hash(

pattern[”trigger_conditions”],

pattern[”action_target”]

)

now = datetime.now().timestamp()

with self.db.get_connection() as conn:

# Check if pattern already exists

result = conn.execute(

text(f”SELECT pattern_id, occurrence_count FROM {TABLE_PATTERNS} WHERE pattern_hash = :hash”),

{”hash”: pattern_hash}

)

existing = result.fetchone()

if existing:

# Update existing pattern

pattern_id = existing[0]

new_count = existing[1] + pattern.get(”occurrence_count”, 1)

conn.execute(text(f”“”

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

“”“), {

“confidence”: pattern[”confidence”],

“support”: pattern[”support”],

“lift”: pattern.get(”lift”),

“conviction”: pattern.get(”conviction”),

“score”: pattern[”pattern_score”],

“last_seen”: now,

“count”: new_count,

“updated_at”: now,

“id”: pattern_id

})

conn.commit()

_LOGGER.debug(f”Updated existing pattern {pattern_id}”)

return pattern_id

else:

# Insert new pattern

result = conn.execute(text(f”“”

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

“”“), {

“type”: pattern[”pattern_type”],

“hash”: pattern_hash,

“triggers”: json.dumps(pattern[”trigger_conditions”]),

“action”: json.dumps(pattern[”action_target”]),

“confidence”: pattern[”confidence”],

“support”: pattern[”support”],

“lift”: pattern.get(”lift”),

“conviction”: pattern.get(”conviction”),

“score”: pattern[”pattern_score”],

“first_seen”: now,

“last_seen”: now,

“count”: pattern.get(”occurrence_count”, 1),

“created_at”: now,

“updated_at”: now

})

conn.commit()

# Get the inserted ID

pattern_id = result.lastrowid

_LOGGER.info(f”Stored new pattern {pattern_id} (score: {pattern[’pattern_score’]:.2f})”)

return pattern_id

def _calculate_pattern_hash(self, triggers, action) -> str:

“”“

Calculate a deterministic hash for pattern deduplication.

The hash is based on the structure of triggers and action,

not on the exact JSON representation (which might vary).

“”“

# Sort triggers for consistent hashing

trigger_sig = json.dumps(sorted(json.dumps(triggers)), sort_keys=True)

action_sig = json.dumps(action, sort_keys=True)

combined = f”{trigger_sig}|{action_sig}”

return hashlib.sha256(combined.encode()).hexdigest()[:16]

def get_patterns(

self,

min_score: float = 0.0,

pattern_type: str = None,

status: str = STATUS_ACTIVE,

feedback: str = None,

limit: int = None

) -> List[Dict]:

“”“

Retrieve patterns with filters.

Args:

min_score: Minimum pattern score

pattern_type: Filter by type (’association’, ‘sequence’, etc.)

status: Pattern status filter

feedback: User feedback filter

limit: Maximum results

Returns:

List of pattern dictionaries

“”“

query = f”SELECT * FROM {TABLE_PATTERNS} WHERE pattern_score >= :min_score”

params = {”min_score”: min_score}

if pattern_type:

query += “ AND pattern_type = :type”

params[”type”] = pattern_type

if status:

query += “ AND status = :status”

params[”status”] = status

if feedback:

query += “ AND user_feedback = :feedback”

params[”feedback”] = feedback

query += “ ORDER BY pattern_score DESC”

if limit:

query += f” LIMIT :limit”

params[”limit”] = limit

with self.db.get_connection() as conn:

result = conn.execute(text(query), params)

patterns = []

for row in result:

pattern = {

“pattern_id”: row[0],

“pattern_type”: row[1],

“pattern_hash”: row[2],

“trigger_conditions”: json.loads(row[3]),

“action_target”: json.loads(row[4]),

“confidence”: row[5],

“support”: row[6],

“lift”: row[7],

“conviction”: row[8],

“pattern_score”: row[9],

“first_seen”: row[10],

“last_seen”: row[11],

“occurrence_count”: row[12],

“user_feedback”: row[13],

“automation_id”: row[14],

“suggestion_shown”: row[15],

“status”: row[16],

“deprecated_by”: row[17],

“created_at”: row[18],

“updated_at”: row[19],

}

patterns.append(pattern)

return patterns

def update_pattern_feedback(self, pattern_id: int, feedback: str):

“”“

Record user feedback on a pattern.

Args:

pattern_id: Pattern to update

feedback: ‘approved’, ‘rejected’, or ‘ignored’

“”“

with self.db.get_connection() as conn:

conn.execute(text(f”“”

UPDATE {TABLE_PATTERNS}

SET user_feedback = :feedback,

updated_at = :updated_at

WHERE pattern_id = :id

“”“), {

“feedback”: feedback,

“updated_at”: datetime.now().timestamp(),

“id”: pattern_id

})

conn.commit()

_LOGGER.info(f”Updated pattern {pattern_id} feedback: {feedback}”)

def mark_pattern_suggested(self, pattern_id: int):

“”“Mark that a pattern suggestion has been shown to user.”“”

with self.db.get_connection() as conn:

conn.execute(text(f”“”

UPDATE {TABLE_PATTERNS}

SET suggestion_shown = 1,

updated_at = :updated_at

WHERE pattern_id = :id

“”“), {

“updated_at”: datetime.now().timestamp(),

“id”: pattern_id

})

conn.commit()

def store_transaction(self, transaction: Dict) -> int:

“”“

Store a transaction for pattern mining.

Transactions are used as input for association rule learning.

Returns:

transaction_id

“”“

now = datetime.now().timestamp()

with self.db.get_connection() as conn:

result = conn.execute(text(f”“”

INSERT INTO {TABLE_TRANSACTIONS} (

window_start, window_end, context_day_type,

context_time_bucket, items, quality_score, created_at

) VALUES (

:start, :end, :day_type, :time_bucket,

:items, :quality, :created_at

)

“”“), {

“start”: transaction[”window_start”],

“end”: transaction[”window_end”],

“day_type”: transaction.get(”context_day_type”),

“time_bucket”: transaction.get(”context_time_bucket”),

“items”: json.dumps(transaction[”items”]),

“quality”: transaction.get(”quality_score”),

“created_at”: now

})

conn.commit()

return result.lastrowid

def get_transactions(

self,

start_time: float = None,

end_time: float = None,

context_filter: Dict = None

) -> List[Dict]:

“”“

Retrieve transactions for analysis.

Args:

start_time: Filter transactions after this timestamp

end_time: Filter transactions before this timestamp

context_filter: Dict with day_type and/or time_bucket

Returns:

List of transaction dictionaries

“”“

query = f”SELECT * FROM {TABLE_TRANSACTIONS} WHERE 1=1”

params = {}

if start_time:

query += “ AND window_start >= :start”

params[”start”] = start_time

if end_time:

query += “ AND window_end <= :end”

params[”end”] = end_time

if context_filter:

if “day_type” in context_filter:

query += “ AND context_day_type = :day_type”

params[”day_type”] = context_filter[”day_type”]

if “time_bucket” in context_filter:

query += “ AND context_time_bucket = :time_bucket”

params[”time_bucket”] = context_filter[”time_bucket”]

query += “ ORDER BY window_start”

with self.db.get_connection() as conn:

result = conn.execute(text(query), params)

transactions = []

for row in result:

transaction = {

“transaction_id”: row[0],

“window_start”: row[1],

“window_end”: row[2],

“context_day_type”: row[3],

“context_time_bucket”: row[4],

“items”: json.loads(row[5]),

“quality_score”: row[6],

“created_at”: row[7],

}

transactions.append(transaction)

return transactions

def clear_all_patterns(self):

“”“Clear all pattern data. Use with caution.”“”

with self.db.get_connection() as conn:

conn.execute(text(f”DELETE FROM {TABLE_SEQUENCES}”))

conn.execute(text(f”DELETE FROM {TABLE_PATTERNS}”))

conn.execute(text(f”DELETE FROM {TABLE_TRANSACTIONS}”))

conn.commit()

_LOGGER.warning(”All pattern data cleared”)

def get_statistics(self) -> Dict:

“”“Get pattern database statistics.”“”

with self.db.get_connection() as conn:

# Count patterns by type and status

result = conn.execute(text(f”“”

SELECT pattern_type, status, COUNT(*), AVG(pattern_score)

FROM {TABLE_PATTERNS}

GROUP BY pattern_type, status

“”“))

stats = {

“by_type_status”: {},

“total_patterns”: 0,

“total_transactions”: 0,

}

for row in result:

key = f”{row[0]}_{row[1]}”

stats[”by_type_status”][key] = {

“count”: row[2],

“avg_score”: round(row[3], 3) if row[3] else 0

}

stats[”total_patterns”] += row[2]

# Count transactions

result = conn.execute(text(f”SELECT COUNT(*) FROM {TABLE_TRANSACTIONS}”))

stats[”total_transactions”] = result.scalar()

return stats
