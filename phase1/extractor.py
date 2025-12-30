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
