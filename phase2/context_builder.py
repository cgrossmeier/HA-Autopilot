"""
Context vector construction for HA-Autopilot.
Enriches state change events with temporal and environmental context.
"""

from datetime import datetime
from typing import Dict, List, Optional, Generator
import logging

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Builds context vectors for state change events.

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

        Args:
            events: Generator of raw state change events
            concurrent_window: Seconds to consider events as concurrent

        Yields: Enriched event dicts with context vectors
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
            entity_id = event["entity_id"]
            if entity_id in self._last_change:
                event["seconds_since_last_change"] = ts - self._last_change[entity_id]
            else:
                event["seconds_since_last_change"] = None
            self._last_change[entity_id] = ts

            # Buffer events for concurrent grouping
            event_buffer.append(event)

            # Process buffer when we have enough events or time gap is large
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
        Call this after build_context_vectors for additional enrichment.
        """
        # Time of day buckets
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
