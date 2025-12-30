"""
Sequential pattern mining for HA Autopilot.

Discovers multi-step behavioral routines where order matters.

Example patterns:
- Morning routine: coffee_maker:on → bathroom_light:on (5min) → thermostat:heat (10min)
- Leaving home: lights:off → lock:locked → garage:closed
- Movie time: TV:on → lights:20% → blinds:closed

Uses PrefixSpan algorithm for efficient sequence mining.
"""

import sys
sys.path.insert(0, '/config/ha_autopilot')

import logging
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from datetime import datetime
from dataclasses import dataclass

from .const import PATTERN_TYPE_SEQUENCE

_LOGGER = logging.getLogger(__name__)


# ============================================================================
# Configuration and Thresholds
# ============================================================================

class SequenceConfig:
    """Configuration for sequence mining."""
    
    # Sequence constraints
    DEFAULT_MAX_LENGTH = 6
    DEFAULT_MIN_GAP_SECONDS = 10
    DEFAULT_MAX_GAP_SECONDS = 1800  # 30 minutes
    
    # Support thresholds
    DEFAULT_MIN_SUPPORT = 0.15
    MIN_ABSOLUTE_OCCURRENCES = 3
    
    # Scoring weights
    CONFIDENCE_WEIGHT = 0.40
    SUPPORT_WEIGHT = 0.30
    COMPLEXITY_WEIGHT = 0.20
    RESPONSIVENESS_WEIGHT = 0.10
    
    # Scoring thresholds
    MAX_SUPPORT_FOR_BONUS = 30
    SIMPLE_SEQUENCE_LENGTH = 4
    QUICK_RESPONSE_THRESHOLD = 300  # 5 minutes
    
    # Score adjustments
    SIMPLE_SEQUENCE_BONUS = 1.0
    COMPLEX_SEQUENCE_PENALTY = 0.7
    QUICK_RESPONSE_BONUS = 1.0
    SLOW_RESPONSE_PENALTY = 0.5
    
    # Variance normalization
    VARIANCE_NORMALIZATION_FACTOR = 100
    
    # Support normalization
    SUPPORT_DIVISOR = 100.0


@dataclass
class SequenceTiming:
    """Timing information for a sequence instance."""
    start_time: float
    gaps: List[int]
    total_duration: int
    
    @property
    def start_hour(self) -> int:
        """Hour of day when sequence started."""
        return datetime.fromtimestamp(self.start_time).hour


@dataclass
class SequenceStep:
    """A single step in a sequence."""
    entity_id: str
    state: str
    typical_delay_seconds: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        result = {
            "entity_id": self.entity_id,
            "state": self.state
        }
        if self.typical_delay_seconds is not None:
            result["typical_delay_seconds"] = self.typical_delay_seconds
        return result
    
    @classmethod
    def from_event(cls, event: Dict) -> 'SequenceStep':
        """Create from event dictionary."""
        return cls(
            entity_id=event["entity_id"],
            state=event["new_state"]
        )
    
    def __str__(self) -> str:
        """String representation for sequence keys."""
        return f"{self.entity_id}:{self.state}"


# ============================================================================
# Sequence Miner
# ============================================================================

class SequenceMiner:
    """
    Discovers sequential patterns in state change events.
    
    A sequential pattern is an ordered list of events that occur
    repeatedly with consistent timing.
    
    Args:
        max_sequence_length: Maximum steps in a sequence (default 6)
        min_gap_seconds: Minimum time between steps (default 10)
        max_gap_seconds: Maximum time between steps (default 1800)
        min_support: Minimum occurrence frequency (default 0.15)
    """
    
    def __init__(
        self,
        max_sequence_length: int = SequenceConfig.DEFAULT_MAX_LENGTH,
        min_gap_seconds: int = SequenceConfig.DEFAULT_MIN_GAP_SECONDS,
        max_gap_seconds: int = SequenceConfig.DEFAULT_MAX_GAP_SECONDS,
        min_support: float = SequenceConfig.DEFAULT_MIN_SUPPORT
    ):
        self.max_sequence_length = max_sequence_length
        self.min_gap_seconds = min_gap_seconds
        self.max_gap_seconds = max_gap_seconds
        self.min_support = min_support
        self.config = SequenceConfig()
    
    # ========================================================================
    # Main Mining Pipeline
    # ========================================================================
    
    def mine_sequences(self, events: List[Dict]) -> List[Dict]:
        """
        Mine sequential patterns from events.
        
        Algorithm:
        1. Group events by day
        2. For each day, find candidate sequences
        3. Count sequence occurrences across all days
        4. Filter by minimum support
        5. Calculate timing statistics
        
        Args:
            events: List of state change events
            
        Returns:
            List of discovered sequence patterns
        """
        if not events:
            return []
        
        _LOGGER.info(f"Mining sequences from {len(events)} events")
        
        by_date = self._group_events_by_date(events)
        _LOGGER.info(f"Analyzing {len(by_date)} days of data")
        
        sequence_counts = self._find_all_sequences(by_date)
        patterns = self._filter_and_convert_sequences(sequence_counts, len(by_date))
        
        _LOGGER.info(f"Discovered {len(patterns)} sequential patterns")
        return patterns
    
    def _group_events_by_date(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """Group events by date for daily pattern detection."""
        by_date = defaultdict(list)
        
        for event in events:
            date = event.get(
                "date",
                datetime.fromtimestamp(event["timestamp"]).strftime("%Y-%m-%d")
            )
            by_date[date].append(event)
        
        return by_date
    
    def _find_all_sequences(
        self,
        by_date: Dict[str, List[Dict]]
    ) -> Dict[str, List[SequenceTiming]]:
        """Find all candidate sequences across all days."""
        sequence_counts = defaultdict(list)
        
        for date, day_events in by_date.items():
            day_events.sort(key=lambda e: e["timestamp"])
            day_sequences = self._find_day_sequences(day_events)
            
            for seq_key, timing in day_sequences:
                sequence_counts[seq_key].append(timing)
        
        return sequence_counts
    
    def _filter_and_convert_sequences(
        self,
        sequence_counts: Dict[str, List[SequenceTiming]],
        total_days: int
    ) -> List[Dict]:
        """Filter sequences by support and convert to pattern format."""
        min_occurrences = self._calculate_min_occurrences(total_days)
        patterns = []
        
        for seq_key, timings in sequence_counts.items():
            if len(timings) < min_occurrences:
                continue
            
            pattern = self._sequence_to_pattern(seq_key, timings)
            patterns.append(pattern)
        
        return patterns
    
    def _calculate_min_occurrences(self, total_days: int) -> int:
        """Calculate minimum occurrences required for a valid pattern."""
        return max(
            self.config.MIN_ABSOLUTE_OCCURRENCES,
            int(self.min_support * total_days)
        )
    
    # ========================================================================
    # Daily Sequence Finding
    # ========================================================================
    
    def _find_day_sequences(
        self,
        events: List[Dict]
    ) -> List[Tuple[str, SequenceTiming]]:
        """
        Find all valid sequences within a single day's events.
        
        Returns:
            List of (sequence_key, timing_info) tuples
        """
        sequences = []
        
        for i in range(len(events)):
            day_sequences = self._find_sequences_starting_at(events, i)
            sequences.extend(day_sequences)
        
        return sequences
    
    def _find_sequences_starting_at(
        self,
        events: List[Dict],
        start_idx: int
    ) -> List[Tuple[str, SequenceTiming]]:
        """Find all valid sequences starting from a specific event."""
        sequences = []
        sequence = [events[start_idx]]
        last_ts = events[start_idx]["timestamp"]
        
        for j in range(start_idx + 1, len(events)):
            gap = events[j]["timestamp"] - last_ts
            
            # Check if we should continue building this sequence
            if not self._should_continue_sequence(gap, len(sequence)):
                break
            
            # Skip events that are too close
            if gap < self.min_gap_seconds:
                continue
            
            # Add event to sequence
            sequence.append(events[j])
            last_ts = events[j]["timestamp"]
            
            # Store if sequence is valid (at least 2 steps)
            if len(sequence) >= 2:
                seq_key = self._create_sequence_key(sequence)
                timing = self._extract_timing(sequence)
                sequences.append((seq_key, timing))
        
        return sequences
    
    def _should_continue_sequence(self, gap: float, current_length: int) -> bool:
        """Check if sequence building should continue."""
        if gap > self.max_gap_seconds:
            return False
        
        if current_length >= self.max_sequence_length:
            return False
        
        return True
    
    # ========================================================================
    # Sequence Key and Timing
    # ========================================================================
    
    def _create_sequence_key(self, sequence: List[Dict]) -> str:
        """
        Generate a unique key for a sequence.
        
        Format: "entity1:state1 -> entity2:state2 -> ..."
        """
        steps = [SequenceStep.from_event(event) for event in sequence]
        return " -> ".join(str(step) for step in steps)
    
    def _extract_timing(self, sequence: List[Dict]) -> SequenceTiming:
        """Extract timing information from a sequence instance."""
        timestamps = [e["timestamp"] for e in sequence]
        gaps = [
            int(timestamps[i] - timestamps[i-1])
            for i in range(1, len(timestamps))
        ]
        
        return SequenceTiming(
            start_time=timestamps[0],
            gaps=gaps,
            total_duration=int(timestamps[-1] - timestamps[0])
        )
    
    # ========================================================================
    # Pattern Conversion
    # ========================================================================
    
    def _sequence_to_pattern(
        self,
        seq_key: str,
        timings: List[SequenceTiming]
    ) -> Dict:
        """
        Convert a discovered sequence to pattern format.
        
        Calculates:
        - Typical gap durations (median)
        - Confidence (consistency of gaps)
        - Support (frequency of occurrence)
        - Pattern score
        """
        steps = self._parse_sequence_steps(seq_key)
        typical_gaps = self._calculate_typical_gaps(timings)
        self._attach_delays_to_steps(steps, typical_gaps)
        
        confidence = self._calculate_sequence_confidence(timings)
        support = len(timings)
        pattern_score = self._calculate_pattern_score(
            confidence,
            support,
            len(steps),
            typical_gaps
        )
        typical_hour = self._calculate_typical_start_hour(timings)
        
        return {
            "pattern_type": PATTERN_TYPE_SEQUENCE,
            "trigger_conditions": [steps[0].to_dict()],
            "action_target": {
                "sequence_steps": [step.to_dict() for step in steps[1:]],
            },
            "confidence": round(confidence, 3),
            "support": support / self.config.SUPPORT_DIVISOR,
            "pattern_score": round(pattern_score, 3),
            "occurrence_count": len(timings),
            "typical_start_hour": typical_hour,
            "sequence_key": seq_key
        }
    
    def _parse_sequence_steps(self, seq_key: str) -> List[SequenceStep]:
        """Parse sequence key into SequenceStep objects."""
        step_strings = seq_key.split(" -> ")
        steps = []
        
        for step_str in step_strings:
            entity_id, state = step_str.split(':', 1)
            steps.append(SequenceStep(entity_id=entity_id, state=state))
        
        return steps
    
    def _calculate_typical_gaps(self, timings: List[SequenceTiming]) -> List[int]:
        """Calculate typical gap durations across all sequence occurrences."""
        if not timings:
            return []
        
        all_gaps = [timing.gaps for timing in timings]
        num_gaps = len(all_gaps[0])
        
        typical_gaps = []
        for gap_idx in range(num_gaps):
            gaps_at_position = [gaps[gap_idx] for gaps in all_gaps]
            typical_gaps.append(int(sum(gaps_at_position) / len(gaps_at_position)))
        
        return typical_gaps
    
    def _attach_delays_to_steps(
        self,
        steps: List[SequenceStep],
        typical_gaps: List[int]
    ):
        """Attach typical delay information to steps."""
        for i in range(1, len(steps)):
            steps[i].typical_delay_seconds = typical_gaps[i - 1]
    
    def _calculate_typical_start_hour(self, timings: List[SequenceTiming]) -> int:
        """Calculate typical hour when sequence starts."""
        start_hours = [timing.start_hour for timing in timings]
        return int(sum(start_hours) / len(start_hours))
    
    # ========================================================================
    # Scoring and Confidence
    # ========================================================================
    
    def _calculate_sequence_confidence(self, timings: List[SequenceTiming]) -> float:
        """
        Calculate confidence based on timing consistency.
        
        More consistent timing = higher confidence.
        """
        all_gaps = [timing.gaps for timing in timings]
        timing_variance = self._calculate_timing_variance(all_gaps)
        
        # Normalize variance to confidence score
        confidence = 1.0 / (1.0 + timing_variance / self.config.VARIANCE_NORMALIZATION_FACTOR)
        return confidence
    
    def _calculate_timing_variance(self, all_gaps: List[List[int]]) -> float:
        """
        Calculate variance in timing across sequence occurrences.
        
        Lower variance = more consistent routine = higher confidence.
        """
        if not all_gaps or len(all_gaps) < 2:
            return 0.0
        
        variances = []
        for gap_idx in range(len(all_gaps[0])):
            gaps_at_position = [gaps[gap_idx] for gaps in all_gaps]
            variance = self._calculate_variance(gaps_at_position)
            variances.append(variance)
        
        return sum(variances) / len(variances)
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values."""
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / len(values)
    
    def _calculate_pattern_score(
        self,
        confidence: float,
        support: int,
        step_count: int,
        typical_gaps: List[int]
    ) -> float:
        """
        Calculate overall pattern score.
        
        Considers:
        - Confidence (timing consistency)
        - Support (occurrence frequency)
        - Complexity (prefer shorter sequences)
        - Responsiveness (prefer quick first response)
        """
        confidence_score = confidence
        support_score = self._normalize_support(support)
        complexity_score = self._calculate_complexity_score(step_count)
        responsiveness_score = self._calculate_responsiveness_score(typical_gaps)
        
        return (
            self.config.CONFIDENCE_WEIGHT * confidence_score +
            self.config.SUPPORT_WEIGHT * support_score +
            self.config.COMPLEXITY_WEIGHT * complexity_score +
            self.config.RESPONSIVENESS_WEIGHT * responsiveness_score
        )
    
    def _normalize_support(self, support: int) -> float:
        """Normalize support to 0-1 scale, capped at threshold."""
        return min(support / self.config.MAX_SUPPORT_FOR_BONUS, 1.0)
    
    def _calculate_complexity_score(self, step_count: int) -> float:
        """Calculate score adjustment based on sequence complexity."""
        if step_count <= self.config.SIMPLE_SEQUENCE_LENGTH:
            return self.config.SIMPLE_SEQUENCE_BONUS
        else:
            return self.config.COMPLEX_SEQUENCE_PENALTY
    
    def _calculate_responsiveness_score(self, typical_gaps: List[int]) -> float:
        """Calculate score adjustment based on first response time."""
        if not typical_gaps:
            return self.config.QUICK_RESPONSE_BONUS
        
        first_gap = typical_gaps[0]
        if first_gap < self.config.QUICK_RESPONSE_THRESHOLD:
            return self.config.QUICK_RESPONSE_BONUS
        else:
            return self.config.SLOW_RESPONSE_PENALTY
