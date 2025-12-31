"""
State change extraction for HA-Autopilot.
Pulls meaningful state transitions from Home Assistant's recorder database.
"""

from sqlalchemy import text
from typing import List, Dict, Generator, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class StateExtractor:
    """
    Extracts state change events from Home Assistant database.

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

        Uses a window function to compare each state with its predecessor,
        yielding only rows where the state actually changed.

        Args:
            entity_ids: List of entity IDs to extract
            start_time: Start of extraction window (default: 30 days ago)
            end_time: End of extraction window (default: now)

        Yields: Dict with entity_id, old_state, new_state, timestamp
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
        """
        # Build parameterized query
        # Using LAG to compare with previous state

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

        Returns: Dict mapping entity_id to current state
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

        Args:
            entity_ids: Entities to query
            target_ts: Unix timestamp

        Returns: Dict mapping entity_id to state at that time
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
