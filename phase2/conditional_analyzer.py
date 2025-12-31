#!/usr/bin/env python3
"""
Conditional Pattern Analyzer for HA-Autopilot Phase 2

Detects conditional patterns like:
- "When door opens AND time > 6 PM → lights turn on"
- "When someone home AND office occupied → climate on"
- "When TV on AND after sunset → lights dim"

Finds patterns that require multiple conditions to be true.
"""

import json
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any, Set
from dataclasses import dataclass
import math


@dataclass
class ConditionalPattern:
    """Represents a detected conditional pattern"""
    conditions: List[Dict[str, Any]]  # List of required conditions
    action_entity: str
    action_state: str
    confidence: float
    occurrences: int
    total_opportunities: int
    description: str
    pattern_type: str  # 'time_and_state', 'presence_and_state', 'multi_state'


class ConditionalAnalyzer:
    """Analyzes conditional patterns in state change data"""

    def __init__(self, min_confidence: float = 0.90, min_occurrences: int = 5):
        """
        Initialize conditional analyzer

        Args:
            min_confidence: Minimum confidence threshold (0.0-1.0)
            min_occurrences: Minimum times pattern must occur to be valid
        """
        self.min_confidence = min_confidence
        self.min_occurrences = min_occurrences

    def analyze(self, events: List[Dict[str, Any]]) -> List[ConditionalPattern]:
        """
        Analyze events and detect conditional patterns

        Args:
            events: List of state change events from Phase 1

        Returns:
            List of detected conditional patterns
        """
        print(f"\n⚙️  Analyzing conditional patterns (min confidence: {self.min_confidence*100}%)...")

        patterns = []

        # Group events by entity/state for actions
        action_events = defaultdict(list)
        for event in events:
            key = (event['entity_id'], event['new_state'])
            action_events[key].append(event)

        # Analyze each potential action
        for (action_entity, action_state), act_events in action_events.items():
            if len(act_events) < self.min_occurrences:
                continue

            # Find time-based conditions
            patterns.extend(
                self._find_time_conditions(action_entity, action_state, act_events)
            )

            # Find presence-based conditions
            patterns.extend(
                self._find_presence_conditions(action_entity, action_state, act_events)
            )

            # Find state-based conditions
            patterns.extend(
                self._find_state_conditions(action_entity, action_state, act_events)
            )

        # Sort by confidence, then occurrences
        patterns.sort(key=lambda p: (p.confidence, p.occurrences), reverse=True)

        # Remove redundant patterns
        patterns = self._remove_redundant_patterns(patterns)

        print(f"✓ Found {len(patterns)} conditional patterns with {self.min_confidence*100}%+ confidence")

        return patterns

    def _find_time_conditions(self, action_entity: str, action_state: str,
                             events: List[Dict]) -> List[ConditionalPattern]:
        """Find patterns like: When X happens AND time is Y"""
        patterns = []

        # Check for evening patterns (after 6 PM)
        evening_events = [e for e in events if e['hour'] >= 18]
        if len(evening_events) >= self.min_occurrences:
            confidence = self._calculate_confidence(len(evening_events), len(events))
            if confidence >= self.min_confidence:
                pattern = ConditionalPattern(
                    conditions=[
                        {'type': 'time', 'operator': '>=', 'hour': 18}
                    ],
                    action_entity=action_entity,
                    action_state=action_state,
                    confidence=confidence,
                    occurrences=len(evening_events),
                    total_opportunities=len(events),
                    description=self._generate_description(
                        [{'type': 'time', 'desc': 'after 6 PM'}],
                        action_entity, action_state, confidence, len(evening_events)
                    ),
                    pattern_type='time_and_state'
                )
                patterns.append(pattern)

        # Check for morning patterns (before 9 AM)
        morning_events = [e for e in events if e['hour'] < 9]
        if len(morning_events) >= self.min_occurrences:
            confidence = self._calculate_confidence(len(morning_events), len(events))
            if confidence >= self.min_confidence:
                pattern = ConditionalPattern(
                    conditions=[
                        {'type': 'time', 'operator': '<', 'hour': 9}
                    ],
                    action_entity=action_entity,
                    action_state=action_state,
                    confidence=confidence,
                    occurrences=len(morning_events),
                    total_opportunities=len(events),
                    description=self._generate_description(
                        [{'type': 'time', 'desc': 'before 9 AM'}],
                        action_entity, action_state, confidence, len(morning_events)
                    ),
                    pattern_type='time_and_state'
                )
                patterns.append(pattern)

        # Check for sunset patterns
        sunset_events = [e for e in events if e.get('sun_position') == 'below_horizon']
        if len(sunset_events) >= self.min_occurrences:
            confidence = self._calculate_confidence(len(sunset_events), len(events))
            if confidence >= self.min_confidence:
                pattern = ConditionalPattern(
                    conditions=[
                        {'type': 'sun', 'position': 'below_horizon'}
                    ],
                    action_entity=action_entity,
                    action_state=action_state,
                    confidence=confidence,
                    occurrences=len(sunset_events),
                    total_opportunities=len(events),
                    description=self._generate_description(
                        [{'type': 'sun', 'desc': 'after sunset'}],
                        action_entity, action_state, confidence, len(sunset_events)
                    ),
                    pattern_type='time_and_state'
                )
                patterns.append(pattern)

        return patterns

    def _find_presence_conditions(self, action_entity: str, action_state: str,
                                  events: List[Dict]) -> List[ConditionalPattern]:
        """Find patterns like: When X happens AND someone is home"""
        patterns = []

        # Check for "someone home" condition
        home_events = [e for e in events if e.get('anyone_home')]
        if len(home_events) >= self.min_occurrences:
            confidence = self._calculate_confidence(len(home_events), len(events))
            if confidence >= self.min_confidence:
                pattern = ConditionalPattern(
                    conditions=[
                        {'type': 'presence', 'condition': 'anyone_home', 'value': True}
                    ],
                    action_entity=action_entity,
                    action_state=action_state,
                    confidence=confidence,
                    occurrences=len(home_events),
                    total_opportunities=len(events),
                    description=self._generate_description(
                        [{'type': 'presence', 'desc': 'someone is home'}],
                        action_entity, action_state, confidence, len(home_events)
                    ),
                    pattern_type='presence_and_state'
                )
                patterns.append(pattern)

        # Check for "everyone home" condition
        all_home_events = [e for e in events if e.get('people_home', 0) >= 2]
        if len(all_home_events) >= self.min_occurrences:
            confidence = self._calculate_confidence(len(all_home_events), len(events))
            if confidence >= self.min_confidence:
                pattern = ConditionalPattern(
                    conditions=[
                        {'type': 'presence', 'condition': 'people_home', 'operator': '>=', 'value': 2}
                    ],
                    action_entity=action_entity,
                    action_state=action_state,
                    confidence=confidence,
                    occurrences=len(all_home_events),
                    total_opportunities=len(events),
                    description=self._generate_description(
                        [{'type': 'presence', 'desc': 'everyone is home'}],
                        action_entity, action_state, confidence, len(all_home_events)
                    ),
                    pattern_type='presence_and_state'
                )
                patterns.append(pattern)

        return patterns

    def _find_state_conditions(self, action_entity: str, action_state: str,
                               events: List[Dict]) -> List[ConditionalPattern]:
        """Find patterns like: When X happens AND Y is in state Z"""
        patterns = []

        # Analyze concurrent states to find correlations
        concurrent_state_counts = defaultdict(lambda: defaultdict(int))

        for event in events:
            concurrent = event.get('concurrent_states', {})
            for entity_id, state in concurrent.items():
                # Skip same entity and person entities (handled separately)
                if entity_id == action_entity or entity_id.startswith('person.'):
                    continue
                concurrent_state_counts[entity_id][state] += 1

        # Find strong concurrent state correlations
        for entity_id, state_counts in concurrent_state_counts.items():
            for state, count in state_counts.items():
                if count >= self.min_occurrences:
                    confidence = self._calculate_confidence(count, len(events))
                    if confidence >= self.min_confidence:
                        pattern = ConditionalPattern(
                            conditions=[
                                {'type': 'state', 'entity_id': entity_id, 'state': state}
                            ],
                            action_entity=action_entity,
                            action_state=action_state,
                            confidence=confidence,
                            occurrences=count,
                            total_opportunities=len(events),
                            description=self._generate_description(
                                [{'type': 'state', 'desc': f"{entity_id.replace('_', ' ').title()} is '{state}'"}],
                                action_entity, action_state, confidence, count
                            ),
                            pattern_type='multi_state'
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

    def _generate_description(self, conditions: List[Dict], action_entity: str,
                             action_state: str, confidence: float, occurrences: int) -> str:
        """Generate human-readable pattern description"""
        action_name = action_entity.replace('_', ' ').title()

        # Format conditions
        condition_strs = [c['desc'] for c in conditions]
        if len(condition_strs) == 1:
            condition_text = condition_strs[0]
        else:
            condition_text = ' AND '.join(condition_strs)

        return (f"When {condition_text} ⟹ "
                f"{action_name} → '{action_state}' "
                f"({int(confidence*100)}% confidence, {occurrences}×)")

    def _remove_redundant_patterns(self, patterns: List[ConditionalPattern]) -> List[ConditionalPattern]:
        """Remove redundant patterns (keep highest confidence version)"""
        seen = set()
        unique_patterns = []

        for pattern in patterns:
            # Create key from conditions + action
            cond_key = tuple(sorted(
                (c.get('type'), c.get('entity_id', ''), c.get('state', ''), c.get('hour', ''))
                for c in pattern.conditions
            ))
            key = (cond_key, pattern.action_entity, pattern.action_state)

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
    analyzer = ConditionalAnalyzer(min_confidence=0.90, min_occurrences=5)
    patterns = analyzer.analyze(events)

    # Display results
    print(f"\n{'='*80}")
    print(f"CONDITIONAL PATTERNS DETECTED: {len(patterns)}")
    print(f"{'='*80}\n")

    for i, pattern in enumerate(patterns[:20], 1):  # Show top 20
        print(f"{i:2d}. {pattern.description}")
