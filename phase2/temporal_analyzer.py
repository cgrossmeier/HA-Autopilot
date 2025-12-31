#!/usr/bin/env python3
"""
Temporal Pattern Analyzer for HA-Autopilot Phase 2

Detects time-based patterns like:
- "Light X turns on at 4:15 PM on weekdays"
- "Blinds close at sunset every day"
- "HVAC adjusts at 9 PM on weekends"

Uses statistical analysis to find patterns with high confidence.
"""

import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any
from dataclasses import dataclass
import math


@dataclass
class TemporalPattern:
    """Represents a detected temporal pattern"""
    entity_id: str
    target_state: str
    hour: int
    minute_range: tuple  # (start, end) in minutes
    days_of_week: List[int]  # 0=Mon, 6=Sun
    confidence: float
    occurrences: int
    total_opportunities: int
    description: str
    pattern_type: str  # 'daily', 'weekday', 'weekend', 'specific_day'


class TemporalAnalyzer:
    """Analyzes temporal patterns in state change data"""

    def __init__(self, min_confidence: float = 0.90, min_occurrences: int = 5):
        """
        Initialize temporal analyzer

        Args:
            min_confidence: Minimum confidence threshold (0.0-1.0)
            min_occurrences: Minimum times pattern must occur to be valid
        """
        self.min_confidence = min_confidence
        self.min_occurrences = min_occurrences

    def analyze(self, events: List[Dict[str, Any]]) -> List[TemporalPattern]:
        """
        Analyze events and detect temporal patterns

        Args:
            events: List of state change events from Phase 1

        Returns:
            List of detected temporal patterns
        """
        print(f"\n🔍 Analyzing temporal patterns (min confidence: {self.min_confidence*100}%)...")

        # Group events by entity and target state
        entity_state_events = defaultdict(list)

        for event in events:
            key = (event['entity_id'], event['new_state'])
            entity_state_events[key].append(event)

        patterns = []

        # Analyze each entity/state combination
        for (entity_id, target_state), entity_events in entity_state_events.items():
            if len(entity_events) < self.min_occurrences:
                continue

            # Find time-based patterns
            patterns.extend(self._find_time_patterns(entity_id, target_state, entity_events, events))

        # Sort by confidence, then occurrences
        patterns.sort(key=lambda p: (p.confidence, p.occurrences), reverse=True)

        print(f"✓ Found {len(patterns)} temporal patterns with {self.min_confidence*100}%+ confidence")

        return patterns

    def _find_time_patterns(self, entity_id: str, target_state: str,
                           entity_events: List[Dict], all_events: List[Dict]) -> List[TemporalPattern]:
        """Find patterns based on time of day and day of week"""
        patterns = []

        # Get date range from events
        dates = set(event['date'] for event in all_events)
        min_date = min(datetime.fromisoformat(d) for d in dates)
        max_date = max(datetime.fromisoformat(d) for d in dates)
        total_days = (max_date - min_date).days + 1

        # Group events by hour
        hour_events = defaultdict(list)
        for event in entity_events:
            hour_events[event['hour']].append(event)

        # Analyze each hour
        for hour, events_in_hour in hour_events.items():
            if len(events_in_hour) < self.min_occurrences:
                continue

            # Check for daily pattern
            pattern = self._check_daily_pattern(
                entity_id, target_state, hour, events_in_hour, total_days
            )
            if pattern and pattern.confidence >= self.min_confidence:
                patterns.append(pattern)

            # Check for weekday/weekend patterns
            weekday_events = [e for e in events_in_hour if not e['is_weekend']]
            weekend_events = [e for e in events_in_hour if e['is_weekend']]

            # Weekday pattern
            if len(weekday_events) >= self.min_occurrences:
                weekdays = [0, 1, 2, 3, 4]  # Mon-Fri
                num_weekdays = sum(1 for d in self._date_range(min_date, max_date)
                                  if d.weekday() in weekdays)
                pattern = self._create_pattern(
                    entity_id, target_state, hour, weekday_events,
                    num_weekdays, weekdays, 'weekday'
                )
                if pattern and pattern.confidence >= self.min_confidence:
                    patterns.append(pattern)

            # Weekend pattern
            if len(weekend_events) >= self.min_occurrences:
                weekends = [5, 6]  # Sat-Sun
                num_weekends = sum(1 for d in self._date_range(min_date, max_date)
                                  if d.weekday() in weekends)
                pattern = self._create_pattern(
                    entity_id, target_state, hour, weekend_events,
                    num_weekends, weekends, 'weekend'
                )
                if pattern and pattern.confidence >= self.min_confidence:
                    patterns.append(pattern)

            # Specific day patterns (e.g., every Monday)
            day_events = defaultdict(list)
            for event in events_in_hour:
                day_events[event['day_of_week']].append(event)

            for day_of_week, day_specific_events in day_events.items():
                if len(day_specific_events) >= self.min_occurrences:
                    num_days = sum(1 for d in self._date_range(min_date, max_date)
                                  if d.weekday() == day_of_week)
                    pattern = self._create_pattern(
                        entity_id, target_state, hour, day_specific_events,
                        num_days, [day_of_week], 'specific_day'
                    )
                    if pattern and pattern.confidence >= self.min_confidence:
                        patterns.append(pattern)

        return patterns

    def _check_daily_pattern(self, entity_id: str, target_state: str, hour: int,
                            events: List[Dict], total_days: int) -> TemporalPattern:
        """Check if events happen daily at this hour"""
        return self._create_pattern(
            entity_id, target_state, hour, events, total_days,
            list(range(7)), 'daily'
        )

    def _create_pattern(self, entity_id: str, target_state: str, hour: int,
                       events: List[Dict], total_opportunities: int,
                       days_of_week: List[int], pattern_type: str) -> TemporalPattern:
        """Create a temporal pattern with confidence calculation"""

        if total_opportunities == 0:
            return None

        occurrences = len(events)

        # Calculate confidence using binomial proportion
        # Wilson score interval for 95% confidence
        confidence = self._calculate_confidence(occurrences, total_opportunities)

        # Find minute range (cluster events within hour)
        minutes = [e['minute'] for e in events]
        min_minute = min(minutes)
        max_minute = max(minutes)
        avg_minute = int(sum(minutes) / len(minutes))

        # Use average minute for tight clusters, range for spread events
        if max_minute - min_minute <= 10:
            minute_range = (avg_minute, avg_minute)
        else:
            minute_range = (min_minute, max_minute)

        # Generate description
        description = self._generate_description(
            entity_id, target_state, hour, minute_range,
            days_of_week, pattern_type, confidence, occurrences
        )

        return TemporalPattern(
            entity_id=entity_id,
            target_state=target_state,
            hour=hour,
            minute_range=minute_range,
            days_of_week=days_of_week,
            confidence=confidence,
            occurrences=occurrences,
            total_opportunities=total_opportunities,
            description=description,
            pattern_type=pattern_type
        )

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

    def _generate_description(self, entity_id: str, target_state: str,
                             hour: int, minute_range: tuple, days_of_week: List[int],
                             pattern_type: str, confidence: float, occurrences: int) -> str:
        """Generate human-readable pattern description"""

        # Format time
        if minute_range[0] == minute_range[1]:
            time_str = f"{hour:02d}:{minute_range[0]:02d}"
        else:
            time_str = f"{hour:02d}:{minute_range[0]:02d}-{minute_range[1]:02d}"

        # Format days
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        if pattern_type == 'daily':
            day_str = "every day"
        elif pattern_type == 'weekday':
            day_str = "on weekdays"
        elif pattern_type == 'weekend':
            day_str = "on weekends"
        elif pattern_type == 'specific_day':
            day_str = f"every {day_names[days_of_week[0]]}"
        else:
            day_str = ', '.join(day_names[d] for d in days_of_week)

        # Friendly entity name
        entity_name = entity_id.replace('_', ' ').title()

        return (f"{entity_name} → '{target_state}' at {time_str} {day_str} "
                f"({int(confidence*100)}% confidence, {occurrences} times)")

    @staticmethod
    def _date_range(start_date: datetime, end_date: datetime):
        """Generate range of dates"""
        for n in range((end_date - start_date).days + 1):
            yield start_date + timedelta(n)


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
    analyzer = TemporalAnalyzer(min_confidence=0.90, min_occurrences=5)
    patterns = analyzer.analyze(events)

    # Display results
    print(f"\n{'='*80}")
    print(f"TEMPORAL PATTERNS DETECTED: {len(patterns)}")
    print(f"{'='*80}\n")

    for i, pattern in enumerate(patterns[:20], 1):  # Show top 20
        print(f"{i:2d}. {pattern.description}")
