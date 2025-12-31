"""
Noise reduction for HA-Autopilot.
Filters out unreliable or uninformative state changes.
"""

from typing import List, Dict, Generator
from collections import defaultdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class NoiseFilter:
    """
    Filters noise from extracted state change events.
    """

    def __init__(self,
                 flap_threshold: int = 5,
                 flap_window: int = 60,
                 min_events_per_entity: int = 5,
                 exclude_unavailable_transitions: bool = True):
        """
        Args:
            flap_threshold: Max state changes per entity within flap_window before marking as flapping
            flap_window: Seconds to consider for flapping detection
            min_events_per_entity: Exclude entities with fewer events than this
            exclude_unavailable_transitions: Filter out transitions to/from unavailable
        """
        self.flap_threshold = flap_threshold
        self.flap_window = flap_window
        self.min_events_per_entity = min_events_per_entity
        self.exclude_unavailable_transitions = exclude_unavailable_transitions

    def filter_events(self, events: List[Dict]) -> List[Dict]:
        """
        Apply all noise filters to a list of events.

        Returns: Filtered list with quality markers
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

        Returns: List of (start_ts, end_ts) tuples for flap periods
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
        Higher scores indicate more reliable/meaningful events.
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
