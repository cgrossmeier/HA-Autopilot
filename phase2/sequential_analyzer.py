#!/usr/bin/env python3
"""
Sequential Pattern Analyzer for HA-Autopilot Phase 2

Detects sequential patterns like:
- "TV turns on → within 2 minutes → lights dim"
- "Door opens → within 5 minutes → motion detected"
- "Person arrives home → scene activates"

Finds causal relationships between events using time windows.
"""

import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import math


@dataclass
class SequentialPattern:
    """Represents a detected sequential pattern"""
    trigger_entity: str
    trigger_state: str
    action_entity: str
    action_state: str
    time_window_seconds: int  # Max seconds between events
    avg_delay_seconds: float  # Average delay when it happens
    confidence: float
    occurrences: int
    total_opportunities: int
    description: str


class SequentialAnalyzer:
    """Analyzes sequential patterns in state change data"""

    def __init__(self, min_confidence: float = 0.90, min_occurrences: int = 5,
                 max_window: int = 300):  # 5 minutes default
        """
        Initialize sequential analyzer

        Args:
            min_confidence: Minimum confidence threshold (0.0-1.0)
            min_occurrences: Minimum times pattern must occur to be valid
            max_window: Maximum time window (seconds) to consider causal
        """
        self.min_confidence = min_confidence
        self.min_occurrences = min_occurrences
        self.max_window = max_window

    def analyze(self, events: List[Dict[str, Any]]) -> List[SequentialPattern]:
        """
        Analyze events and detect sequential patterns

        Args:
            events: List of state change events from Phase 1

        Returns:
            List of detected sequential patterns
        """
        print(f"\n🔗 Analyzing sequential patterns (max window: {self.max_window}s)...")

        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e['timestamp'])

        # Build index for fast lookup
        entity_events = defaultdict(list)
        for event in sorted_events:
            entity_events[event['entity_id']].append(event)

        patterns = []

        # For each potential trigger entity/state
        trigger_combos = defaultdict(list)
        for event in sorted_events:
            key = (event['entity_id'], event['new_state'])
            trigger_combos[key].append(event)

        # Analyze each potential trigger
        for (trigger_entity, trigger_state), trigger_events in trigger_combos.items():
            if len(trigger_events) < self.min_occurrences:
                continue

            # Look for actions that follow this trigger
            patterns.extend(
                self._find_sequential_actions(
                    trigger_entity, trigger_state, trigger_events,
                    sorted_events
                )
            )

        # Sort by confidence, then occurrences
        patterns.sort(key=lambda p: (p.confidence, p.occurrences), reverse=True)

        # Remove redundant patterns (keep highest confidence)
        patterns = self._remove_redundant_patterns(patterns)

        print(f"✓ Found {len(patterns)} sequential patterns with {self.min_confidence*100}%+ confidence")

        return patterns

    def _find_sequential_actions(self, trigger_entity: str, trigger_state: str,
                                trigger_events: List[Dict],
                                all_events: List[Dict]) -> List[SequentialPattern]:
        """Find actions that consistently follow a trigger"""
        patterns = []

        # Build index of events by entity for faster lookup
        event_index = defaultdict(list)
        for event in all_events:
            event_index[event['entity_id']].append(event)

        # Track what happens after each trigger
        action_followers = defaultdict(list)  # (action_entity, action_state) -> [delays]

        for trigger_event in trigger_events:
            trigger_time = trigger_event['timestamp']

            # Look at all other entities' events in the time window
            for entity_id, entity_event_list in event_index.items():
                # Skip same entity
                if entity_id == trigger_entity:
                    continue

                # Find events after trigger within window
                for action_event in entity_event_list:
                    action_time = action_event['timestamp']
                    delay = action_time - trigger_time

                    # Must be after trigger and within window
                    if 0 < delay <= self.max_window:
                        key = (entity_id, action_event['new_state'])
                        action_followers[key].append((delay, trigger_event, action_event))
                        break  # Only count first event per entity after trigger

        # Analyze each potential action
        for (action_entity, action_state), occurrences_data in action_followers.items():
            if len(occurrences_data) < self.min_occurrences:
                continue

            delays = [d[0] for d in occurrences_data]
            avg_delay = sum(delays) / len(delays)

            # Calculate confidence: how often does action follow trigger?
            occurrences = len(occurrences_data)
            total_opportunities = len(trigger_events)

            confidence = self._calculate_confidence(occurrences, total_opportunities)

            if confidence >= self.min_confidence:
                # Determine optimal time window (90th percentile of delays)
                sorted_delays = sorted(delays)
                window = int(sorted_delays[int(len(sorted_delays) * 0.9)])

                pattern = SequentialPattern(
                    trigger_entity=trigger_entity,
                    trigger_state=trigger_state,
                    action_entity=action_entity,
                    action_state=action_state,
                    time_window_seconds=window,
                    avg_delay_seconds=avg_delay,
                    confidence=confidence,
                    occurrences=occurrences,
                    total_opportunities=total_opportunities,
                    description=self._generate_description(
                        trigger_entity, trigger_state, action_entity, action_state,
                        window, avg_delay, confidence, occurrences
                    )
                )
                patterns.append(pattern)

        return patterns

    def _calculate_confidence(self, successes: int, trials: int) -> float:
        """
        Calculate confidence using Wilson score interval
        Returns the lower bound of 95% confidence interval
        """
        if trials == 0:
            return 0.0

        p = successes / trials

        # Edge case: perfect success rate
        if p == 1.0:
            # Conservative estimate for perfect scores
            return max(0.0, 1.0 - (2.0 / trials))

        # Edge case: perfect failure rate
        if p == 0.0:
            return 0.0

        z = 1.96  # 95% confidence

        denominator = 1 + z**2 / trials
        center = (p + z**2 / (2*trials)) / denominator

        # Calculate margin with protection against negative sqrt
        sqrt_term = max(0.0, p*(1-p)/trials + z**2/(4*trials**2))
        margin = (z / denominator) * math.sqrt(sqrt_term)

        # Return lower bound (conservative estimate)
        return max(0.0, min(1.0, center - margin))

    def _generate_description(self, trigger_entity: str, trigger_state: str,
                             action_entity: str, action_state: str,
                             window: int, avg_delay: float,
                             confidence: float, occurrences: int) -> str:
        """Generate human-readable pattern description"""

        # Friendly names
        trigger_name = trigger_entity.replace('_', ' ').title()
        action_name = action_entity.replace('_', ' ').title()

        # Format delay
        if avg_delay < 60:
            delay_str = f"{int(avg_delay)}s"
        else:
            delay_str = f"{int(avg_delay/60)}m {int(avg_delay%60)}s"

        window_str = f"{int(window)}s" if window < 60 else f"{int(window/60)}m"

        return (f"{trigger_name} → '{trigger_state}' ⟹ "
                f"{action_name} → '{action_state}' "
                f"(within {window_str}, avg {delay_str}, "
                f"{int(confidence*100)}% confidence, {occurrences}× )")

    def _remove_redundant_patterns(self, patterns: List[SequentialPattern]) -> List[SequentialPattern]:
        """Remove redundant patterns (keep highest confidence version)"""
        seen = set()
        unique_patterns = []

        for pattern in patterns:
            key = (pattern.trigger_entity, pattern.trigger_state,
                   pattern.action_entity, pattern.action_state)

            if key not in seen:
                seen.add(key)
                unique_patterns.append(pattern)

        return unique_patterns


if __name__ == '__main__':
    # Test with Phase 1 data
    import glob

    # Load most recent export
    export_files = sorted(glob.glob('/config/ha_autopilot/exports/state_changes_*.jsonl'))
    if not export_files:
        print("No export files found")
        exit(1)

    latest_file = export_files[-1]
    print(f"Loading {latest_file}...")

    events = []
    with open(latest_file, 'r') as f:
        for line in f:
            events.append(json.loads(line))

    print(f"Loaded {len(events)} events")

    # Run analysis
    analyzer = SequentialAnalyzer(min_confidence=0.90, min_occurrences=5, max_window=300)
    patterns = analyzer.analyze(events)

    # Display results
    print(f"\n{'='*80}")
    print(f"SEQUENTIAL PATTERNS DETECTED: {len(patterns)}")
    print(f"{'='*80}\n")

    for i, pattern in enumerate(patterns[:20], 1):  # Show top 20
        print(f"{i:2d}. {pattern.description}")
