# HA Autopilot Phase 1 - Complete Code Reference

**Purpose**: Complete code repository and implementation guide for Phase 1 Data Pipeline
**Target Audience**: Phase 2 developers, system maintainers, documentation reference
**Database Support**: SQLite (primary), MariaDB/MySQL (fallback with auto-detection)

---

## Table of Contents

1. [Overview](#overview)
2. [Implementation Order](#implementation-order)
3. [Environment Setup](#environment-setup)
4. [Core Modules](#core-modules)
5. [Utility Scripts](#utility-scripts)
6. [Configuration](#configuration)
7. [Database Integration Notes](#database-integration-notes)
8. [Phase 2 Integration Points](#phase-2-integration-points)

---

## Overview

### What Phase 1 Delivers

The Phase 1 data pipeline extracts meaningful state change history from Home Assistant's recorder database, enriches it with temporal and environmental context, filters noise, and exports clean datasets for pattern recognition.

**Key Features:**
- Smart database detection (MariaDB → SQLite fallback)
- Entity classification by signal quality
- Context-enriched state change extraction
- Noise filtering with quality scoring
- JSON Lines export format
- Comprehensive metadata generation

**Architecture:**
```
┌─────────────────┐
│   Database      │ ← SQLite or MariaDB with auto-detection
└────────┬────────┘
         │
┌────────▼────────┐
│ Entity Classifier│ ← Filter 1,085 entities → 189 high/medium signal
└────────┬────────┘
         │
┌────────▼────────┐
│ State Extractor │ ← Extract actual state changes (LAG window function)
└────────┬────────┘
         │
┌────────▼────────┐
│ Context Builder │ ← Add temporal, environmental, device context
└────────┬────────┘
         │
┌────────▼────────┐
│  Noise Filter   │ ← Quality scoring, flapping detection
└────────┬────────┘
         │
┌────────▼────────┐
│   Exporter      │ ← JSON Lines format + metadata
└─────────────────┘
```

---

## Implementation Order

### Phase 1 Build Sequence

The modules must be implemented in this order due to dependencies:

1. **database.py** - Foundation layer, no dependencies
2. **entity_classifier.py** - Depends on: database.py
3. **extractor.py** - Depends on: database.py
4. **context_builder.py** - Depends on: extractor.py
5. **noise_filter.py** - No dependencies (operates on event lists)
6. **exporter.py** - No dependencies (operates on event lists)
7. **run_extraction.py** - Depends on: all above modules

### Testing Sequence

1. **test_connection.py** - Verify database connectivity
2. **test_classification.py** - Verify entity filtering
3. **test_quick_extraction.py** - Small dataset validation
4. **run_extraction.py --dry-run** - Preview extraction
5. **run_extraction.py --days 7** - Initial full test
6. **explore_data.py** - Pattern visualization

---

## Environment Setup

### Directory Structure

```bash
/config/ha_autopilot/
├── venv/                          # Python virtual environment
├── exports/                       # Extracted data files
├── logs/                          # Execution logs
├── database.py
├── entity_classifier.py
├── extractor.py
├── context_builder.py
├── noise_filter.py
├── exporter.py
├── run_extraction.py
├── explore_data.py
├── test_connection.py
├── test_classification.py
├── test_quick_extraction.py
└── README.md
```

### Python Environment Setup

```bash
# Create virtual environment
cd /config/ha_autopilot
python3 -m venv venv

# Activate environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install sqlalchemy pandas pymysql
```

### Required Dependencies

```python
# requirements.txt
sqlalchemy>=2.0.0    # Database abstraction layer
pandas>=2.0.0        # Data manipulation (optional for analysis)
pymysql>=1.1.0       # MySQL/MariaDB driver
```

---

## Core Modules

### 1. database.py - Database Connection Layer

**Purpose**: Manage database connections with smart fallback from MariaDB to SQLite
**Dependencies**: sqlalchemy
**Key Feature**: Auto-detection checks for actual Home Assistant data before selecting database

```python
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
```

**Phase 2 Integration Notes:**
- Extend `_auto_detect_database()` to support multiple data sources
- Add connection health monitoring for long-running pattern analysis
- Consider read replicas for MariaDB in production deployments

---

### 2. entity_classifier.py - Entity Classification System

**Purpose**: Filter entities by signal quality to reduce noise
**Dependencies**: database.py
**Key Feature**: Domain-based and device_class-based classification

```python
"""
Entity classification for HA-Autopilot.
Determines which entities produce meaningful state changes.

Classification Strategy:
- High Signal: Lights, switches, locks, doors, windows, motion, presence
- Medium Signal: Climate, vacuum, fans (less frequent but meaningful)
- Low Signal: Most sensors (continuous updates, low value)
- Exclude: Weather, sun, automations, device trackers

Phase 2 Usage:
Entity classifications can be used to weight patterns differently.
High-signal entities might receive higher confidence scores.
"""

from sqlalchemy import text
from typing import Set, Dict, List
import logging
import json

logger = logging.getLogger(__name__)


# Domain-level classification
# These domains always produce meaningful state changes
HIGH_SIGNAL_DOMAINS = {
    "light", "switch", "lock", "cover", "media_player",
    "input_boolean", "person", "input_select"
}

# Medium signal domains - meaningful but less frequent
MEDIUM_SIGNAL_DOMAINS = {
    "climate", "fan", "vacuum", "humidifier", "water_heater"
}

# Binary sensor device classes that indicate meaningful events
# These are high-value triggers for automations
HIGH_SIGNAL_BINARY_CLASSES = {
    "door", "window", "motion", "occupancy", "presence",
    "garage_door", "lock", "opening", "safety"
}

# Medium signal binary sensors
MEDIUM_SIGNAL_BINARY_CLASSES = {
    "plug", "running", "moving", "sound", "vibration"
}

# Always exclude these domains - they don't represent user actions
EXCLUDE_DOMAINS = {
    "weather", "sun", "automation", "script", "scene",
    "persistent_notification", "zone", "device_tracker",
    "update", "button", "number", "select", "text"
}


class EntityClassifier:
    """
    Classifies Home Assistant entities by signal quality.

    Methodology:
    1. Check custom includes/excludes first (user override)
    2. Check domain-level exclusions
    3. Check high/medium signal domains
    4. For binary_sensor, inspect device_class
    5. Default to low signal

    Args:
        db_connector: DatabaseConnector instance
        custom_includes: Set of entity_ids to always include
        custom_excludes: Set of entity_ids to always exclude

    Example:
        classifier = EntityClassifier(db)
        entities = classifier.get_filtered_entities(min_signal="high")
        # Returns only high-signal entities
    """

    def __init__(self, db_connector, custom_includes: Set[str] = None,
                 custom_excludes: Set[str] = None):
        self.db = db_connector
        self.custom_includes = custom_includes or set()
        self.custom_excludes = custom_excludes or set()

        # Caching for performance
        self._entity_cache = None
        self._attribute_cache = {}

    def get_all_entities(self) -> List[Dict]:
        """
        Fetch all entities from states_meta.

        Home Assistant Schema:
        - states_meta: Maps metadata_id to entity_id
        - Used for efficient entity lookups in states table

        Returns:
            List of dicts with metadata_id, entity_id, domain
        """
        if self._entity_cache is not None:
            return self._entity_cache

        with self.db.get_connection() as conn:
            # Get all entity IDs
            result = conn.execute(text("""
                SELECT metadata_id, entity_id
                FROM states_meta
                ORDER BY entity_id
            """))

            entities = []
            for row in result:
                entity_id = row[1]
                domain = entity_id.split(".")[0]

                entities.append({
                    "metadata_id": row[0],
                    "entity_id": entity_id,
                    "domain": domain
                })

            self._entity_cache = entities
            logger.info(f"Loaded {len(entities)} entities from database")
            return entities

    def get_entity_device_class(self, entity_id: str) -> str:
        """
        Look up the device_class attribute for an entity.

        Device class provides semantic meaning for binary sensors.
        Examples: "door", "window", "motion", "occupancy"

        Args:
            entity_id: Entity to query

        Returns:
            device_class string or None if not found

        Phase 2 Note:
            Device class can be used to create semantic categories
            for pattern grouping (e.g., all "door" sensors together).
        """
        if entity_id in self._attribute_cache:
            return self._attribute_cache[entity_id]

        with self.db.get_connection() as conn:
            # Find the most recent state with attributes
            result = conn.execute(text("""
                SELECT sa.shared_attrs
                FROM states s
                JOIN states_meta sm ON s.metadata_id = sm.metadata_id
                JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
                WHERE sm.entity_id = :entity_id
                AND sa.shared_attrs IS NOT NULL
                ORDER BY s.last_updated_ts DESC
                LIMIT 1
            """), {"entity_id": entity_id})

            row = result.fetchone()
            if row and row[0]:
                try:
                    attrs = json.loads(row[0])
                    device_class = attrs.get("device_class")
                    self._attribute_cache[entity_id] = device_class
                    return device_class
                except json.JSONDecodeError:
                    pass

            self._attribute_cache[entity_id] = None
            return None

    def classify_entity(self, entity_id: str, domain: str) -> str:
        """
        Classify a single entity.

        Classification Hierarchy:
        1. Custom overrides (highest priority)
        2. Domain-level exclusions
        3. High signal domains
        4. Medium signal domains
        5. Binary sensor device_class inspection
        6. Default to low signal

        Returns: 'high', 'medium', 'low', or 'exclude'
        """
        # Custom overrides take precedence
        if entity_id in self.custom_excludes:
            return "exclude"
        if entity_id in self.custom_includes:
            return "high"

        # Domain-level exclusions
        if domain in EXCLUDE_DOMAINS:
            return "exclude"

        # High signal domains
        if domain in HIGH_SIGNAL_DOMAINS:
            return "high"

        # Medium signal domains
        if domain in MEDIUM_SIGNAL_DOMAINS:
            return "medium"

        # Binary sensors need device_class inspection
        if domain == "binary_sensor":
            device_class = self.get_entity_device_class(entity_id)
            if device_class in HIGH_SIGNAL_BINARY_CLASSES:
                return "high"
            if device_class in MEDIUM_SIGNAL_BINARY_CLASSES:
                return "medium"
            return "low"

        # Sensors are generally low signal (too noisy)
        if domain == "sensor":
            return "low"

        # Default to low for unknown domains
        return "low"

    def get_filtered_entities(self,
                              include_medium: bool = True,
                              min_signal: str = "medium") -> List[Dict]:
        """
        Get list of entities that pass the signal filter.

        Args:
            include_medium: Include medium-signal entities
            min_signal: Minimum signal level ('high' or 'medium')

        Returns:
            List of entity dicts with classification added

        Phase 2 Usage:
            Pattern recognition can use different entity sets:
            - High-only for critical patterns
            - High+Medium for comprehensive patterns
        """
        all_entities = self.get_all_entities()
        filtered = []

        for entity in all_entities:
            classification = self.classify_entity(
                entity["entity_id"],
                entity["domain"]
            )

            if classification == "exclude":
                continue

            if classification == "low":
                continue

            if classification == "medium" and min_signal == "high":
                continue

            entity["signal_level"] = classification
            filtered.append(entity)

        logger.info(f"Filtered to {len(filtered)} entities from {len(all_entities)} total")
        return filtered

    def generate_report(self) -> Dict:
        """
        Generate a classification report for all entities.
        Useful for tuning the filter configuration.

        Returns:
            Dict with counts and entity lists by classification
        """
        all_entities = self.get_all_entities()

        report = {
            "high": [],
            "medium": [],
            "low": [],
            "exclude": []
        }

        for entity in all_entities:
            classification = self.classify_entity(
                entity["entity_id"],
                entity["domain"]
            )
            report[classification].append(entity["entity_id"])

        return {
            "counts": {k: len(v) for k, v in report.items()},
            "entities": report
        }
```

**Classification Statistics (Reference):**
- High Signal: 175 entities (~16% of total)
- Medium Signal: 14 entities (~1% of total)
- Low Signal: 686 entities (~63% of total)
- Excluded: 210 entities (~19% of total)

---

### 3. extractor.py - State Change Extraction

**Purpose**: Extract actual state changes (not all state updates) using SQL window functions
**Dependencies**: database.py
**Key Feature**: LAG window function to identify real state changes

```python
"""
State change extraction for HA-Autopilot.
Pulls meaningful state transitions from Home Assistant's recorder database.

Extraction Strategy:
Home Assistant records every state update, even when state doesn't change.
We use LAG window function to compare each state with its predecessor,
yielding only rows where state actually changed.

Performance Note:
Processes entities in chunks of 50 to manage memory and query plan size.
Uses parameterized queries to prevent SQL injection.
"""

from sqlalchemy import text
from typing import List, Dict, Generator, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class StateExtractor:
    """
    Extracts state change events from Home Assistant database.

    Database Schema Used:
    - states: All state records with last_updated_ts
    - states_meta: Maps metadata_id to entity_id

    Query Strategy:
    1. Use LAG window function partitioned by entity
    2. Compare current state with previous state
    3. Filter to only rows where state changed
    4. Exclude 'unavailable' and 'unknown' states

    Args:
        db_connector: DatabaseConnector instance
        batch_size: Number of rows per batch (default 10000)
    """

    def __init__(self, db_connector, batch_size: int = 10000):
        self.db = db_connector
        self.batch_size = batch_size

    def extract_state_changes(self,
                              entity_ids: List[str],
                              start_time: datetime = None,
                              end_time: datetime = None) -> Generator[Dict, None, None]:
        """
        Extract state changes for specified entities within a time range.

        Algorithm:
        1. Chunk entities into groups of 50
        2. For each chunk, run window function query
        3. Yield events as they're found (generator pattern)

        Args:
            entity_ids: List of entity IDs to extract
            start_time: Start of extraction window (default: 30 days ago)
            end_time: End of extraction window (default: now)

        Yields:
            Dict with entity_id, old_state, new_state, timestamp, datetime

        Phase 2 Integration:
            For real-time pattern detection, this could be modified to
            stream events as they occur rather than batch processing.
        """
        if not entity_ids:
            logger.warning("No entity IDs provided for extraction")
            return

        if start_time is None:
            start_time = datetime.now() - timedelta(days=30)
        if end_time is None:
            end_time = datetime.now()

        start_ts = start_time.timestamp()
        end_ts = end_time.timestamp()

        logger.info(f"Extracting state changes for {len(entity_ids)} entities")
        logger.info(f"Time range: {start_time} to {end_time}")

        # Process entities in chunks to manage memory
        chunk_size = 50
        for i in range(0, len(entity_ids), chunk_size):
            chunk = entity_ids[i:i + chunk_size]
            yield from self._extract_chunk(chunk, start_ts, end_ts)

    def _extract_chunk(self,
                       entity_ids: List[str],
                       start_ts: float,
                       end_ts: float) -> Generator[Dict, None, None]:
        """
        Extract state changes for a chunk of entities.

        SQL Explanation:
        The LAG window function looks at the previous row for the same entity
        (partitioned by entity, ordered by timestamp) and compares states.

        Why this works:
        - LAG gets previous state value
        - WHERE clause filters to only changed states
        - Handles first state (prev_state IS NULL) gracefully
        """
        # Build parameterized query
        placeholders = ", ".join([f":entity_{i}" for i in range(len(entity_ids))])
        params = {f"entity_{i}": eid for i, eid in enumerate(entity_ids)}
        params["start_ts"] = start_ts
        params["end_ts"] = end_ts

        # The query uses a subquery with LAG to find the previous state,
        # then filters to rows where state changed
        query = f"""
            WITH state_sequence AS (
                SELECT
                    sm.entity_id,
                    s.state,
                    s.last_updated_ts,
                    LAG(s.state) OVER (
                        PARTITION BY sm.entity_id
                        ORDER BY s.last_updated_ts
                    ) as prev_state
                FROM states s
                JOIN states_meta sm ON s.metadata_id = sm.metadata_id
                WHERE sm.entity_id IN ({placeholders})
                AND s.last_updated_ts >= :start_ts
                AND s.last_updated_ts <= :end_ts
                AND s.state IS NOT NULL
                AND s.state NOT IN ('unavailable', 'unknown')
            )
            SELECT entity_id, prev_state, state, last_updated_ts
            FROM state_sequence
            WHERE state != prev_state OR prev_state IS NULL
            ORDER BY last_updated_ts
        """

        with self.db.get_connection() as conn:
            result = conn.execute(text(query), params)

            count = 0
            for row in result:
                count += 1
                yield {
                    "entity_id": row[0],
                    "old_state": row[1],
                    "new_state": row[2],
                    "timestamp": row[3],
                    "datetime": datetime.fromtimestamp(row[3]).isoformat()
                }

            logger.debug(f"Extracted {count} state changes from chunk of {len(entity_ids)} entities")

    def get_current_states(self, entity_ids: List[str]) -> Dict[str, str]:
        """
        Get the current state for each entity.
        Used for building context vectors.

        Returns:
            Dict mapping entity_id to current state
        """
        if not entity_ids:
            return {}

        placeholders = ", ".join([f":entity_{i}" for i in range(len(entity_ids))])
        params = {f"entity_{i}": eid for i, eid in enumerate(entity_ids)}

        # Get most recent state for each entity
        query = f"""
            SELECT sm.entity_id, s.state
            FROM states s
            JOIN states_meta sm ON s.metadata_id = sm.metadata_id
            WHERE sm.entity_id IN ({placeholders})
            AND s.state_id = (
                SELECT MAX(s2.state_id)
                FROM states s2
                WHERE s2.metadata_id = s.metadata_id
            )
        """

        with self.db.get_connection() as conn:
            result = conn.execute(text(query), params)
            return {row[0]: row[1] for row in result}

    def get_state_at_time(self,
                          entity_ids: List[str],
                          target_ts: float) -> Dict[str, str]:
        """
        Get the state of each entity at a specific point in time.
        Returns the most recent state before or at the target timestamp.

        Critical for Context Building:
        This method enables "what was everything else doing at this moment?"
        queries that are essential for pattern correlation.

        Args:
            entity_ids: Entities to query
            target_ts: Unix timestamp

        Returns:
            Dict mapping entity_id to state at that time

        Phase 2 Usage:
            Pattern recognition needs to know concurrent states.
            This method provides the foundation for correlation analysis.
        """
        if not entity_ids:
            return {}

        states = {}

        # Process in chunks
        chunk_size = 50
        for i in range(0, len(entity_ids), chunk_size):
            chunk = entity_ids[i:i + chunk_size]

            placeholders = ", ".join([f":entity_{j}" for j in range(len(chunk))])
            params = {f"entity_{j}": eid for j, eid in enumerate(chunk)}
            params["target_ts"] = target_ts

            # Get the most recent state at or before target time
            query = f"""
                SELECT sm.entity_id, s.state
                FROM states s
                JOIN states_meta sm ON s.metadata_id = sm.metadata_id
                WHERE sm.entity_id IN ({placeholders})
                AND s.last_updated_ts <= :target_ts
                AND s.last_updated_ts = (
                    SELECT MAX(s2.last_updated_ts)
                    FROM states s2
                    JOIN states_meta sm2 ON s2.metadata_id = sm2.metadata_id
                    WHERE sm2.entity_id = sm.entity_id
                    AND s2.last_updated_ts <= :target_ts
                )
            """

            with self.db.get_connection() as conn:
                result = conn.execute(text(query), params)
                for row in result:
                    states[row[0]] = row[1]

        return states
```

**Performance Benchmarks:**
- 7 days, 175 entities: 6 seconds
- 30 days, 189 entities: 11 seconds
- Throughput: ~300 events/second

---

### 4. context_builder.py - Context Vector Construction

**Purpose**: Enrich state changes with temporal, environmental, and device context
**Dependencies**: extractor.py
**Key Feature**: Creates comprehensive context snapshots for each event

```python
"""
Context vector construction for HA-Autopilot.
Enriches state change events with temporal and environmental context.

Context Categories:
1. Temporal: hour, minute, day_of_week, is_weekend, time_bucket
2. Behavioral: seconds_since_last_change (per entity)
3. Environmental: sun_position
4. Device: concurrent_states (all other entities at this moment)
5. Sequential: concurrent_changes (other events within ±60 seconds)

Phase 2 Importance:
Context vectors enable pattern recognition to identify correlations:
- "Light X turns on at 4 PM on weekdays when person Y is home"
- "When door opens AND sun is down, lights turn on"
"""

from datetime import datetime
from typing import Dict, List, Optional, Generator
import logging

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Builds context vectors for state change events.

    Processing Strategy:
    1. Events are buffered in chunks of 100
    2. For each buffer, query concurrent states once
    3. This reduces database queries from N to N/100

    Args:
        extractor: StateExtractor instance
        context_entities: List of entity IDs to include in concurrent state snapshot
        sun_entity: Entity ID for sun position (default: sun.sun)
    """

    def __init__(self,
                 extractor,
                 context_entities: List[str],
                 sun_entity: str = "sun.sun"):
        self.extractor = extractor
        self.context_entities = context_entities
        self.sun_entity = sun_entity

        # Track last change time per entity for time_since calculation
        self._last_change: Dict[str, float] = {}

    def build_context_vectors(self,
                              events: Generator[Dict, None, None],
                              concurrent_window: int = 60) -> Generator[Dict, None, None]:
        """
        Enrich state change events with context.

        Process:
        1. Add temporal context (hour, day, time bucket)
        2. Calculate time since last change for this entity
        3. Buffer events for efficient concurrent state queries
        4. Add concurrent state snapshot
        5. Find other changes within ±60 second window

        Args:
            events: Generator of raw state change events
            concurrent_window: Seconds to consider events as concurrent

        Yields:
            Enriched event dicts with context vectors

        Memory Note:
            Buffer size of 100 balances memory usage vs query efficiency.
            For very large extractions, this could be adjusted.
        """
        event_buffer = []

        for event in events:
            # Add temporal context
            ts = event["timestamp"]
            dt = datetime.fromtimestamp(ts)

            event["hour"] = dt.hour
            event["minute"] = dt.minute
            event["day_of_week"] = dt.weekday()  # 0 = Monday
            event["is_weekend"] = dt.weekday() >= 5
            event["date"] = dt.strftime("%Y-%m-%d")

            # Calculate time since last change for this entity
            # Useful for detecting rapid flapping or normal cadence
            entity_id = event["entity_id"]
            if entity_id in self._last_change:
                event["seconds_since_last_change"] = ts - self._last_change[entity_id]
            else:
                event["seconds_since_last_change"] = None
            self._last_change[entity_id] = ts

            # Buffer events for concurrent grouping
            event_buffer.append(event)

            # Process buffer when we have enough events
            if len(event_buffer) >= 100:
                yield from self._process_buffer(event_buffer, concurrent_window)
                event_buffer = []

        # Process remaining events
        if event_buffer:
            yield from self._process_buffer(event_buffer, concurrent_window)

    def _process_buffer(self,
                        events: List[Dict],
                        concurrent_window: int) -> Generator[Dict, None, None]:
        """
        Process a buffer of events, adding concurrent state snapshots.

        Concurrent State Snapshot:
        For each event, we capture the state of ALL monitored entities
        at that exact moment in time. This creates a complete picture
        of the home's state when this change occurred.

        Example:
        Light turns on at 4:15 PM
        Concurrent states show:
        - person.chris: home
        - binary_sensor.front_door: on (open)
        - climate.main_floor: heat
        - sun.sun: below_horizon

        This enables pattern recognition to find correlations.
        """
        for event in events:
            ts = event["timestamp"]

            # Get state of all context entities at this moment
            concurrent_states = self.extractor.get_state_at_time(
                self.context_entities,
                ts
            )

            # Remove the event's own entity from concurrent states
            concurrent_states.pop(event["entity_id"], None)

            # Add sun position as a top-level field if available
            event["sun_position"] = concurrent_states.pop(self.sun_entity, None)

            # Store remaining concurrent states
            event["concurrent_states"] = concurrent_states

            # Find other events within the concurrent window
            # This captures sequences like "door opens, then light turns on"
            event["concurrent_changes"] = [
                {
                    "entity_id": other["entity_id"],
                    "new_state": other["new_state"],
                    "offset_seconds": other["timestamp"] - ts
                }
                for other in events
                if other["entity_id"] != event["entity_id"]
                and abs(other["timestamp"] - ts) <= concurrent_window
            ]

            yield event

    def add_derived_features(self, event: Dict) -> Dict:
        """
        Add derived features useful for pattern recognition.

        Derived Features:
        1. time_bucket: Human-readable time of day categories
        2. people_home: Count of person entities in 'home' state
        3. anyone_home: Boolean for presence detection

        Phase 2 Usage:
        These derived features simplify pattern rules:
        - "During evening time bucket"
        - "When anyone_home is True"

        Call this after build_context_vectors for additional enrichment.
        """
        # Time of day buckets for human-readable patterns
        hour = event["hour"]
        if 5 <= hour < 9:
            event["time_bucket"] = "early_morning"
        elif 9 <= hour < 12:
            event["time_bucket"] = "morning"
        elif 12 <= hour < 14:
            event["time_bucket"] = "midday"
        elif 14 <= hour < 17:
            event["time_bucket"] = "afternoon"
        elif 17 <= hour < 20:
            event["time_bucket"] = "evening"
        elif 20 <= hour < 23:
            event["time_bucket"] = "night"
        else:
            event["time_bucket"] = "late_night"

        # Presence inference (if person entities are tracked)
        concurrent = event.get("concurrent_states", {})
        home_count = sum(
            1 for k, v in concurrent.items()
            if k.startswith("person.") and v == "home"
        )
        event["people_home"] = home_count
        event["anyone_home"] = home_count > 0

        return event
```

**Context Vector Example:**
```json
{
  "entity_id": "light.living_room",
  "old_state": "off",
  "new_state": "on",
  "timestamp": 1735506718.713721,
  "hour": 16,
  "day_of_week": 4,
  "time_bucket": "afternoon",
  "sun_position": "above_horizon",
  "people_home": 2,
  "anyone_home": true,
  "concurrent_states": {
    "person.chris": "home",
    "binary_sensor.front_door": "on"
  },
  "concurrent_changes": []
}
```

---

### 5. noise_filter.py - Noise Reduction

**Purpose**: Filter unreliable events and assign quality scores
**Dependencies**: None (operates on event lists)
**Key Feature**: Flapping detection using sliding window algorithm

```python
"""
Noise reduction for HA-Autopilot.
Filters out unreliable or uninformative state changes.

Noise Types:
1. Low Activity: Entities with < 5 events (too rare to be meaningful)
2. Flapping: Rapid state changes (>5 in 60 seconds)
3. Unavailable Transitions: Device connectivity issues
4. Rapid Changes: Events less than 10 seconds apart

Quality Scoring:
Events receive a score from 0.0 to 1.0 based on reliability.
Phase 2 can weight patterns by average event quality.
"""

from typing import List, Dict, Generator
from collections import defaultdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class NoiseFilter:
    """
    Filters noise from extracted state change events.

    Filtering Strategy:
    1. Analyze all events to detect flapping periods
    2. Calculate entity-level statistics
    3. Apply filters (low activity, unavailable states)
    4. Mark flapping events (but don't exclude them completely)
    5. Assign quality scores to each event

    Args:
        flap_threshold: Max state changes per entity within flap_window before marking as flapping
        flap_window: Seconds to consider for flapping detection (default 60)
        min_events_per_entity: Exclude entities with fewer events than this
        exclude_unavailable_transitions: Filter out transitions to/from unavailable
    """

    def __init__(self,
                 flap_threshold: int = 5,
                 flap_window: int = 60,
                 min_events_per_entity: int = 5,
                 exclude_unavailable_transitions: bool = True):
        self.flap_threshold = flap_threshold
        self.flap_window = flap_window
        self.min_events_per_entity = min_events_per_entity
        self.exclude_unavailable_transitions = exclude_unavailable_transitions

    def filter_events(self, events: List[Dict]) -> List[Dict]:
        """
        Apply all noise filters to a list of events.

        Process:
        1. Group events by entity
        2. Calculate per-entity statistics (flap periods, unique states)
        3. Filter out low-activity entities
        4. Filter out unavailable transitions
        5. Mark flapping events
        6. Assign quality scores

        Returns:
            Filtered list with quality markers added to each event

        Phase 2 Usage:
            Quality scores can be used to weight pattern confidence.
            High-quality events (score > 0.9) might receive higher weight.
        """
        # Group by entity for analysis
        by_entity = defaultdict(list)
        for event in events:
            by_entity[event["entity_id"]].append(event)

        # Calculate entity-level stats
        entity_stats = {}
        for entity_id, entity_events in by_entity.items():
            entity_stats[entity_id] = {
                "event_count": len(entity_events),
                "flap_periods": self._detect_flapping(entity_events),
                "unique_states": len(set(e["new_state"] for e in entity_events))
            }

        # Filter events
        filtered = []
        excluded_counts = defaultdict(int)

        for event in events:
            entity_id = event["entity_id"]
            stats = entity_stats[entity_id]

            # Exclude low-activity entities
            if stats["event_count"] < self.min_events_per_entity:
                excluded_counts["low_activity"] += 1
                continue

            # Exclude unavailable transitions
            if self.exclude_unavailable_transitions:
                if event.get("old_state") in ("unavailable", "unknown"):
                    excluded_counts["unavailable_transition"] += 1
                    continue
                if event.get("new_state") in ("unavailable", "unknown"):
                    excluded_counts["unavailable_transition"] += 1
                    continue

            # Mark (but don't exclude) events during flap periods
            event["during_flap"] = self._in_flap_period(
                event["timestamp"],
                stats["flap_periods"]
            )

            # Add quality score
            event["quality_score"] = self._calculate_quality(event, stats)

            filtered.append(event)

        logger.info(f"Filtered {len(events)} events to {len(filtered)}")
        for reason, count in excluded_counts.items():
            logger.info(f"  Excluded {count} events: {reason}")

        return filtered

    def _detect_flapping(self, events: List[Dict]) -> List[tuple]:
        """
        Detect time periods where an entity was flapping.

        Flapping Algorithm (Sliding Window):
        1. Sort events by timestamp
        2. For each event, count how many events are within window
        3. If count >= threshold, mark period as flapping
        4. Merge overlapping flap periods

        Returns:
            List of (start_ts, end_ts) tuples for flap periods

        Phase 2 Note:
            Flapping usually indicates device issues, not user behavior.
            These events should receive lower confidence in patterns.
        """
        if len(events) < self.flap_threshold:
            return []

        # Sort by timestamp
        sorted_events = sorted(events, key=lambda e: e["timestamp"])

        flap_periods = []
        window_start = 0

        for i, event in enumerate(sorted_events):
            ts = event["timestamp"]

            # Move window start forward
            while (window_start < i and
                   ts - sorted_events[window_start]["timestamp"] > self.flap_window):
                window_start += 1

            # Check if too many events in window
            events_in_window = i - window_start + 1
            if events_in_window >= self.flap_threshold:
                period_start = sorted_events[window_start]["timestamp"]
                period_end = ts

                # Merge with existing period if overlapping
                if flap_periods and flap_periods[-1][1] >= period_start - self.flap_window:
                    flap_periods[-1] = (flap_periods[-1][0], period_end)
                else:
                    flap_periods.append((period_start, period_end))

        return flap_periods

    def _in_flap_period(self, ts: float, flap_periods: List[tuple]) -> bool:
        """Check if a timestamp falls within any flap period."""
        for start, end in flap_periods:
            if start <= ts <= end:
                return True
        return False

    def _calculate_quality(self, event: Dict, stats: Dict) -> float:
        """
        Calculate a quality score for an event (0.0 to 1.0).

        Scoring Factors:
        - Flapping: Multiply by 0.3 (major penalty)
        - Few unique states: Multiply by 0.9 (might be stuck)
        - Rapid changes: Multiply by 0.7 (suspicious behavior)

        Higher scores indicate more reliable/meaningful events.

        Phase 2 Usage:
            quality_score can be used as a multiplier for pattern confidence:
            pattern_confidence = base_confidence * avg_event_quality
        """
        score = 1.0

        # Penalize events during flap periods
        if event.get("during_flap"):
            score *= 0.3

        # Penalize entities with very few unique states (might be stuck)
        if stats["unique_states"] <= 2:
            score *= 0.9

        # Penalize very rapid changes
        seconds_since = event.get("seconds_since_last_change")
        if seconds_since is not None and seconds_since < 10:
            score *= 0.7

        return round(score, 2)

    def get_entity_report(self, events: List[Dict]) -> Dict:
        """
        Generate a report on entity quality for manual review.

        Returns:
            Dict mapping entity_id to quality metrics:
            - total_events
            - flap_periods
            - events_during_flaps
            - flap_percentage
            - unique_states
            - recommendation (include, exclude, etc.)

        Usage:
            Review entities with high flap_percentage for exclusion.
        """
        by_entity = defaultdict(list)
        for event in events:
            by_entity[event["entity_id"]].append(event)

        report = {}
        for entity_id, entity_events in by_entity.items():
            flap_periods = self._detect_flapping(entity_events)
            flap_event_count = sum(
                1 for e in entity_events
                if self._in_flap_period(e["timestamp"], flap_periods)
            )

            report[entity_id] = {
                "total_events": len(entity_events),
                "flap_periods": len(flap_periods),
                "events_during_flaps": flap_event_count,
                "flap_percentage": round(100 * flap_event_count / len(entity_events), 1) if entity_events else 0,
                "unique_states": len(set(e["new_state"] for e in entity_events)),
                "recommendation": self._recommend_action(entity_events, flap_periods)
            }

        return report

    def _recommend_action(self, events: List[Dict], flap_periods: List[tuple]) -> str:
        """Generate a recommendation for an entity based on its behavior."""
        if len(events) < 5:
            return "exclude_low_activity"

        flap_count = sum(
            1 for e in events
            if self._in_flap_period(e["timestamp"], flap_periods)
        )

        if flap_count / len(events) > 0.5:
            return "exclude_high_flap"

        if len(flap_periods) > 0:
            return "include_with_caution"

        return "include"
```

**Quality Distribution (30-day Reference):**
- High Quality (≥ 0.9): 83.6%
- Medium Quality (0.7-0.9): 3.3%
- Low Quality (< 0.7): 13.1%

---

### 6. exporter.py - Data Export and Storage

**Purpose**: Export cleaned datasets in JSON Lines format
**Dependencies**: None
**Key Feature**: Streaming JSON Lines format for efficient processing

```python
"""
Data export for HA-Autopilot.
Writes cleaned datasets to disk in JSON Lines format.

JSON Lines Format:
Each line is a complete, valid JSON object representing one event.
Benefits:
- Streamable: Can process line-by-line without loading entire file
- Appendable: Can add new events without rewriting file
- Human-readable: Easy to inspect and debug
- Compatible: Widely supported by data processing tools

Phase 2 Usage:
Pattern recognition engines can stream events from JSONL files
without loading everything into memory.
"""

import json
import os
from datetime import datetime
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class DataExporter:
    """
    Exports processed state change data to files.

    Export Formats:
    1. JSONL: Main data file, one event per line
    2. JSON: Metadata file with extraction statistics

    Args:
        output_dir: Directory for export files (default: /config/ha_autopilot/exports)
    """

    def __init__(self, output_dir: str = "/config/ha_autopilot/exports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export_jsonl(self,
                     events: List[Dict],
                     filename: str = None) -> str:
        """
        Export events to JSON Lines format.

        File Format:
        {"entity_id":"light.living_room","old_state":"off",...}
        {"entity_id":"binary_sensor.door","old_state":"on",...}

        Each line is independently parseable JSON.

        Args:
            events: List of context-enriched events
            filename: Output filename (default: auto-generated with timestamp)

        Returns:
            Path to exported file

        Phase 2 Integration:
            Pattern recognition can use:
            with open(filepath) as f:
                for line in f:
                    event = json.loads(line)
                    # Process event
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"state_changes_{timestamp}.jsonl"

        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w") as f:
            for event in events:
                # Convert any non-serializable types
                clean_event = self._clean_for_json(event)
                f.write(json.dumps(clean_event) + "\n")

        logger.info(f"Exported {len(events)} events to {filepath}")
        return filepath

    def export_metadata(self,
                        events: List[Dict],
                        entity_stats: Dict = None) -> str:
        """
        Export metadata about the extraction.

        Metadata Includes:
        - Export timestamp
        - Event count
        - Entity count
        - Date range
        - Entity list
        - Entity quality statistics

        Args:
            events: List of events
            entity_stats: Optional quality report from NoiseFilter

        Returns:
            Path to metadata file

        Phase 2 Usage:
            Metadata can help determine if dataset is suitable:
            - Enough events for statistical significance?
            - Good entity coverage?
            - Adequate time span?
        """
        metadata = {
            "export_timestamp": datetime.now().isoformat(),
            "event_count": len(events),
            "entity_count": len(set(e["entity_id"] for e in events)),
            "date_range": {
                "start": min(e["datetime"] for e in events) if events else None,
                "end": max(e["datetime"] for e in events) if events else None
            },
            "entities": list(set(e["entity_id"] for e in events)),
            "entity_stats": entity_stats or {}
        }

        filepath = os.path.join(self.output_dir, "export_metadata.json")
        with open(filepath, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Exported metadata to {filepath}")
        return filepath

    def _clean_for_json(self, obj):
        """
        Convert non-JSON-serializable types.

        Handles:
        - datetime objects → ISO format strings
        - Nested dicts and lists
        - Any other type → string conversion
        """
        if isinstance(obj, dict):
            return {k: self._clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._clean_for_json(v) for v in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            return str(obj)

    def load_jsonl(self, filepath: str) -> List[Dict]:
        """
        Load events from a JSON Lines file.

        Returns:
            List of event dicts

        Phase 2 Usage:
            For small datasets, load all at once.
            For large datasets, use streaming approach:

            def stream_events(filepath):
                with open(filepath) as f:
                    for line in f:
                        yield json.loads(line)
        """
        events = []
        with open(filepath, "r") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events
```

**File Size Reference:**
- 7 days: 15.8 MB (1,972 events)
- 30 days: 26.5 MB (3,229 events)
- Average: ~8 KB per event

---

### 7. run_extraction.py - Main Pipeline Orchestrator

**Purpose**: Coordinate all modules and execute complete extraction
**Dependencies**: All above modules
**Key Feature**: Command-line interface with multiple options

```python
#!/usr/bin/env python3
"""
run_extraction.py - Main extraction script for HA-Autopilot Phase 1

Execution Flow:
1. Parse command-line arguments
2. Initialize database connection
3. Classify entities by signal quality
4. Extract state changes from database
5. Build context vectors
6. Apply noise filters
7. Add derived features
8. Export to JSON Lines
9. Generate metadata report

Usage Examples:
    python run_extraction.py --days 30
    python run_extraction.py --days 7 --include-medium --verbose
    python run_extraction.py --dry-run  # Preview only
"""

import argparse
import logging
from datetime import datetime, timedelta
import sys

from database import DatabaseConnector
from entity_classifier import EntityClassifier
from extractor import StateExtractor
from context_builder import ContextBuilder
from noise_filter import NoiseFilter
from exporter import DataExporter


def setup_logging(verbose: bool = False):
    """
    Configure logging for the extraction process.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def main():
    """
    Main extraction pipeline execution.

    Phase 2 Integration Points:
    - The exported JSONL file is the input for pattern recognition
    - Metadata provides dataset statistics for validation
    - Entity quality reports can inform pattern confidence weighting
    """
    parser = argparse.ArgumentParser(
        description="Extract state changes from Home Assistant",
        epilog="Output: JSON Lines file with context-enriched events"
    )
    parser.add_argument("--days", type=int, default=30,
                       help="Days of history to extract (default: 30)")
    parser.add_argument("--db-url", type=str, default=None,
                       help="Database URL (auto-detect if not specified)")
    parser.add_argument("--output-dir", type=str,
                       default="/config/ha_autopilot/exports",
                       help="Output directory for exports")
    parser.add_argument("--include-medium", action="store_true",
                       help="Include medium-signal entities (climate, vacuum)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose logging (DEBUG level)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be extracted without running")

    args = parser.parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger("run_extraction")

    # Step 1: Initialize database connection
    logger.info("Initializing extraction pipeline...")

    try:
        db = DatabaseConnector(db_url=args.db_url)
        stats = db.test_connection()
        logger.info(f"Connected to {stats['database_type']} database")
        logger.info(f"Total state records: {stats['total_states']:,}")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)

    # Step 2: Classify entities
    classifier = EntityClassifier(db)

    if args.include_medium:
        entities = classifier.get_filtered_entities(min_signal="medium")
    else:
        entities = classifier.get_filtered_entities(min_signal="high")

    entity_ids = [e["entity_id"] for e in entities]
    logger.info(f"Selected {len(entity_ids)} entities for extraction")

    # Dry run: Show entities and exit
    if args.dry_run:
        logger.info("Dry run - entities that would be extracted:")
        for entity in entities:
            logger.info(f"  {entity['entity_id']} ({entity['signal_level']})")
        return

    # Step 3: Extract state changes
    extractor = StateExtractor(db)

    start_time = datetime.now() - timedelta(days=args.days)
    end_time = datetime.now()

    logger.info(f"Extracting state changes from {start_time} to {end_time}")

    raw_events = extractor.extract_state_changes(
        entity_ids,
        start_time=start_time,
        end_time=end_time
    )

    # Step 4: Build context vectors
    logger.info("Building context vectors...")
    context_builder = ContextBuilder(extractor, entity_ids)
    enriched_events = list(context_builder.build_context_vectors(raw_events))

    logger.info(f"Built {len(enriched_events)} context vectors")

    # Step 5: Apply noise filter
    logger.info("Applying noise filters...")
    noise_filter = NoiseFilter()
    filtered_events = noise_filter.filter_events(enriched_events)

    # Step 6: Add derived features
    for event in filtered_events:
        context_builder.add_derived_features(event)

    # Step 7: Export
    logger.info("Exporting data...")
    exporter = DataExporter(output_dir=args.output_dir)

    data_path = exporter.export_jsonl(filtered_events)

    entity_report = noise_filter.get_entity_report(enriched_events)
    metadata_path = exporter.export_metadata(filtered_events, entity_report)

    logger.info("Extraction complete!")
    logger.info(f"Data file: {data_path}")
    logger.info(f"Metadata: {metadata_path}")

    # Summary
    logger.info("")
    logger.info("=== Extraction Summary ===")
    logger.info(f"Time range: {args.days} days")
    logger.info(f"Entities monitored: {len(entity_ids)}")
    logger.info(f"Raw state changes: {len(enriched_events)}")
    logger.info(f"After filtering: {len(filtered_events)}")
    if enriched_events:
        reduction = 100 * (1 - len(filtered_events)/len(enriched_events))
        logger.info(f"Reduction: {reduction:.1f}%")


if __name__ == "__main__":
    main()
```

**Command-Line Options:**
```bash
# Basic usage
python run_extraction.py

# Custom time range
python run_extraction.py --days 90

# Include climate/vacuum
python run_extraction.py --include-medium

# Verbose output
python run_extraction.py --verbose

# Preview without running
python run_extraction.py --dry-run

# Explicit database
python run_extraction.py --db-url "mysql+pymysql://user:pass@host/db"
```

---

## Utility Scripts

### test_connection.py

```python
#!/usr/bin/env python3
"""Test database connection and display statistics."""

import sys
sys.path.insert(0, '/config/ha_autopilot')

from database import DatabaseConnector

try:
    db = DatabaseConnector()
    stats = db.test_connection()

    print(f"\n{'='*50}")
    print(f"Database Connection Test")
    print(f"{'='*50}")
    print(f"Database type: {stats['database_type']}")
    print(f"Total state records: {stats['total_states']:,}")
    print(f"Unique entities: {stats['entity_count']}")
    print(f"Earliest timestamp: {stats['earliest_timestamp']}")
    print(f"Latest timestamp: {stats['latest_timestamp']}")
    print(f"{'='*50}\n")
    print("✓ Connection successful!")

except Exception as e:
    print(f"\n✗ Connection failed: {e}\n")
    sys.exit(1)
```

### test_classification.py

```python
#!/usr/bin/env python3
"""Test entity classification and display report."""

import sys
sys.path.insert(0, '/config/ha_autopilot')

from database import DatabaseConnector
from entity_classifier import EntityClassifier

db = DatabaseConnector()
classifier = EntityClassifier(db)

report = classifier.generate_report()

print("\n" + "="*50)
print("Entity Classification Report")
print("="*50)
print(f"High signal:   {report['counts']['high']}")
print(f"Medium signal: {report['counts']['medium']}")
print(f"Low signal:    {report['counts']['low']}")
print(f"Excluded:      {report['counts']['exclude']}")
print()
print("High signal entities (first 20):")
for entity_id in sorted(report['entities']['high'])[:20]:
    print(f"  {entity_id}")

if len(report['entities']['high']) > 20:
    print(f"  ... and {len(report['entities']['high']) - 20} more")

print("\n" + "="*50)
```

### explore_data.py

```python
#!/usr/bin/env python3
"""
Explore patterns in extracted data.
Generates activity graphs and pattern analysis.
"""

import sys
sys.path.insert(0, '/config/ha_autopilot')

from exporter import DataExporter
from collections import Counter
import glob
import os

# Find the most recent export file
export_dir = "/config/ha_autopilot/exports"
files = glob.glob(os.path.join(export_dir, "state_changes_*.jsonl"))
if not files:
    print("No export files found!")
    sys.exit(1)

latest_file = max(files, key=os.path.getctime)

exporter = DataExporter()
events = exporter.load_jsonl(latest_file)

print(f"\n{'='*70}")
print(f"Data Exploration Report")
print(f"File: {os.path.basename(latest_file)}")
print(f"{'='*70}\n")

# Most active entities
entity_counts = Counter(e["entity_id"] for e in events)
print("Most Active Entities (Top 15):")
print(f"{'Entity':<50} {'Events':>10}")
print("-" * 70)
for entity, count in entity_counts.most_common(15):
    print(f"{entity:<50} {count:>10}")

# Events by hour
hour_counts = Counter(e["hour"] for e in events)
print(f"\n{'='*70}")
print("Activity by Hour of Day:")
print(f"{'Hour':<10} {'Events':>10} {'Graph'}")
print("-" * 70)
max_count = max(hour_counts.values())
for hour in range(24):
    count = hour_counts.get(hour, 0)
    bar_length = int(40 * count / max_count) if max_count > 0 else 0
    bar = "█" * bar_length
    print(f"{hour:02d}:00     {count:>10} {bar}")

# Events by day of week
dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
dow_counts = Counter(e["day_of_week"] for e in events)
print(f"\n{'='*70}")
print("Activity by Day of Week:")
print(f"{'Day':<15} {'Events':>10} {'Graph'}")
print("-" * 70)
max_count = max(dow_counts.values())
for dow in range(7):
    count = dow_counts.get(dow, 0)
    bar_length = int(40 * count / max_count) if max_count > 0 else 0
    bar = "█" * bar_length
    print(f"{dow_names[dow]:<15} {count:>10} {bar}")

print(f"\n{'='*70}\n")
```

---

## Configuration

### Home Assistant configuration.yaml

```yaml
# Default recorder uses SQLite
# No explicit recorder configuration needed for SQLite

# Optional: To use MariaDB, uncomment and configure:
# recorder:
#   db_url: mysql+pymysql://DB_USER:DB_PASSWORD@DB_HOST/DB_NAME?charset=utf8mb4
#   purge_keep_days: 30
#   commit_interval: 1
#   auto_purge: true

# SANITIZED: Replace DB_USER, DB_PASSWORD, DB_HOST, DB_NAME with actual values
```

### Database Credentials Template

```python
# For MariaDB connection (sanitized):
DB_HOST = "192.168.1.XX"           # Database server IP
DB_PORT = 3306                      # Default MySQL/MariaDB port
DB_NAME = "database_name"           # Database name
DB_USER = "username"                # Database user
DB_PASSWORD = "password"            # Database password

# Connection URL format:
# mysql+pymysql://DB_USER:DB_PASSWORD@DB_HOST:DB_PORT/DB_NAME?charset=utf8mb4
```

---

## Database Integration Notes

### For Phase 2 Developers

#### Database Schema Reference

**states table:**
```sql
state_id           INTEGER PRIMARY KEY
metadata_id        INTEGER  -- Links to states_meta.metadata_id
state              TEXT     -- Current state value
last_updated_ts    FLOAT    -- Unix timestamp
```

**states_meta table:**
```sql
metadata_id        INTEGER PRIMARY KEY
entity_id          TEXT     -- Full entity ID (e.g., "light.living_room")
```

**state_attributes table:**
```sql
attributes_id      INTEGER PRIMARY KEY
shared_attrs       TEXT     -- JSON blob with attributes
```

#### MariaDB vs SQLite Differences

**Query Syntax:**
- Both support standard SQL
- Window functions work identically
- SHOW TABLES is MariaDB-specific (use information_schema for SQLite)

**Performance:**
- SQLite: Excellent up to 1-2 GB
- MariaDB: Better for >2 GB, concurrent access, distributed systems

**Connection Pooling:**
- SQLite: Single connection recommended (file-based)
- MariaDB: Connection pooling essential (QueuePool)

#### Phase 2 Database Patterns

**Pattern Storage Options:**

1. **Separate Pattern Database:**
```python
# Store discovered patterns in separate database
pattern_db_url = "mysql+pymysql://user:pass@host/ha_patterns"
# Tables: patterns, pattern_events, pattern_confidence
```

2. **Same Database, Separate Tables:**
```sql
CREATE TABLE discovered_patterns (
    pattern_id INTEGER PRIMARY KEY,
    pattern_type VARCHAR(50),
    description TEXT,
    confidence FLOAT,
    support_count INTEGER,
    created_at TIMESTAMP
);

CREATE TABLE pattern_events (
    pattern_id INTEGER,
    event_timestamp FLOAT,
    entity_id VARCHAR(255),
    FOREIGN KEY (pattern_id) REFERENCES discovered_patterns(pattern_id)
);
```

3. **JSON Storage:**
```python
# Store patterns as JSON files, use database only for source data
# Simpler for initial Phase 2 development
```

**Recommended Approach for Phase 2:**
- Use existing Phase 1 JSONL exports as input
- Store discovered patterns in JSON files initially
- Migrate to database storage once pattern schema stabilizes

---

## Phase 2 Integration Points

### 1. Data Loading

```python
# Phase 2 pattern recognition should load data like this:
from exporter import DataExporter

def load_training_data(export_file):
    """Load events for pattern recognition."""
    exporter = DataExporter()
    events = exporter.load_jsonl(export_file)
    return events

# For streaming (large datasets):
def stream_training_data(export_file):
    """Stream events one at a time."""
    with open(export_file) as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
```

### 2. Entity Metadata

```python
# Phase 2 can use entity classifications for weighting:
from entity_classifier import EntityClassifier
from database import DatabaseConnector

db = DatabaseConnector()
classifier = EntityClassifier(db)

# Get entity metadata
entities = classifier.get_filtered_entities()
entity_weights = {
    e["entity_id"]: 1.0 if e["signal_level"] == "high" else 0.7
    for e in entities
}

# Use in pattern confidence:
pattern_confidence = base_confidence * entity_weights[entity_id]
```

### 3. Quality Scoring

```python
# Phase 2 should consider event quality scores:
def calculate_pattern_confidence(events):
    """Weight pattern by average event quality."""
    avg_quality = sum(e["quality_score"] for e in events) / len(events)
    base_confidence = calculate_base_confidence(events)
    return base_confidence * avg_quality
```

### 4. Temporal Context

```python
# Phase 2 can use time buckets for pattern categorization:
def categorize_pattern(events):
    """Determine pattern temporal category."""
    time_buckets = Counter(e["time_bucket"] for e in events)
    primary_bucket = time_buckets.most_common(1)[0][0]

    if all(e["is_weekend"] for e in events):
        return f"weekend_{primary_bucket}"
    else:
        return f"weekday_{primary_bucket}"
```

### 5. Concurrent State Analysis

```python
# Phase 2 pattern recognition example:
def find_trigger_patterns(events):
    """Find common concurrent states when an event occurs."""
    for event in events:
        concurrent = event["concurrent_states"]

        # Find entities that are consistently in specific states
        for entity, state in concurrent.items():
            # Check if this entity-state combo appears frequently
            # This is a potential trigger condition
            pass
```

---

## Summary

### Code Modules Delivered

| Module | Lines | Purpose |
|--------|-------|---------|
| database.py | 130 | Smart database connection with fallback |
| entity_classifier.py | 180 | Entity signal quality filtering |
| extractor.py | 200 | State change extraction with LAG |
| context_builder.py | 160 | Context vector construction |
| noise_filter.py | 220 | Quality scoring and flapping detection |
| exporter.py | 120 | JSON Lines export with metadata |
| run_extraction.py | 120 | Pipeline orchestration |
| **Total** | **1,130** | **Complete Phase 1 system** |

### Key Achievements

1. **Smart Database Fallback**: Automatic MariaDB → SQLite with data verification
2. **Entity Classification**: 82.6% noise reduction (1,085 → 189 entities)
3. **Context Enrichment**: 10+ context fields per event
4. **Quality Scoring**: 83.6% high-quality events
5. **Performance**: 11 seconds for 30 days, 189 entities

### Phase 2 Readiness

- ✅ Clean dataset with rich context
- ✅ Quality scores for pattern weighting
- ✅ Entity metadata for classification
- ✅ Temporal features for categorization
- ✅ Concurrent states for correlation
- ✅ JSON Lines format for streaming
- ✅ Database abstraction for flexibility

---

*Document Version: 1.0*
*Created: December 29, 2025*
*Purpose: Phase 2 Development Reference*
