"""
Temporal pattern analysis for HA Autopilot.

Identifies patterns that depend on specific time conditions:
- Fixed schedule patterns (light turns on at 18:30 every day)
- Solar-dependent patterns (outdoor lights at sunset)
- Duration-based patterns (turn off after 4 hours)

Uses statistical time series analysis to find temporal consistency.
"""

import sys
sys.path.insert(0, '/config/ha_autopilot')

import math
import logging
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from datetime import datetime, time
from dataclasses import dataclass

from .const import PATTERN_TYPE_TEMPORAL

_LOGGER = logging.getLogger(__name__)


# ============================================================================
# Configuration and Thresholds
# ============================================================================

class TemporalConfig:
    """Configuration for temporal pattern analysis."""
    
    # Time tolerance
    DEFAULT_TIME_TOLERANCE_MIN = 15
    DEFAULT_SOLAR_TOLERANCE_MIN = 30
    
    # Occurrence thresholds
    DEFAULT_MIN_OCCURRENCES = 10
    MAX_OCCURRENCES_FOR_SCORE = 30
    
    # Statistical thresholds
    COEFFICIENT_VARIATION_THRESHOLD = 0.3
    SOLAR_CONFIDENCE_THRESHOLD = 0.70
    
    # Scoring weights
    CONSISTENCY_WEIGHT = 0.60
    OCCURRENCE_WEIGHT = 0.40
    
    # Support calculation divisor
    SUPPORT_DIVISOR = 100.0
    
    # Valid state transitions
    VALID_STATES = {"on", "off", "open", "closed", "locked", "unlocked"}


@dataclass
class TimeCluster:
    """Represents a cluster of events at similar times."""
    mean_seconds: float
    std_dev_seconds: float
    coefficient_variation: float
    event_count: int
    
    @property
    def mean_time_str(self) -> str:
        """Format mean time as HH:MM."""
        hours = int(self.mean_seconds // 3600)
        minutes = int((self.mean_seconds % 3600) // 60)
        return f"{hours:02d}:{minutes:02d}"
    
    @property
    def std_dev_minutes(self) -> int:
        """Standard deviation in minutes."""
        return int(self.std_dev_seconds / 60)
    
    def is_consistent(self, time_tolerance: float, cv_threshold: float) -> bool:
        """Check if cluster meets consistency requirements."""
        return (
            self.coefficient_variation < cv_threshold and 
            self.std_dev_seconds < time_tolerance
        )


# ============================================================================
# Temporal Pattern Analyzer
# ============================================================================

class TemporalAnalyzer:
    """
    Analyzes time-based patterns in state changes.
    
    Detects three types of temporal patterns:
    1. Fixed Schedule: Events occurring at consistent clock time
    2. Solar Dependent: Events correlating with sunrise/sunset
    3. Duration Based: Actions triggered by state persistence
    
    Args:
        time_tolerance_minutes: Max variation for fixed schedule (default 15)
        min_occurrences: Minimum pattern occurrences (default 10)
        solar_tolerance_minutes: Max variation for solar patterns (default 30)
    """
    
    def __init__(
        self,
        time_tolerance_minutes: int = TemporalConfig.DEFAULT_TIME_TOLERANCE_MIN,
        min_occurrences: int = TemporalConfig.DEFAULT_MIN_OCCURRENCES,
        solar_tolerance_minutes: int = TemporalConfig.DEFAULT_SOLAR_TOLERANCE_MIN
    ):
        self.time_tolerance = time_tolerance_minutes * 60  # Convert to seconds
        self.min_occurrences = min_occurrences
        self.solar_tolerance = solar_tolerance_minutes * 60
        self.config = TemporalConfig()
    
    # ========================================================================
    # Main Analysis Pipeline
    # ========================================================================
    
    def analyze_temporal_patterns(self, events: List[Dict]) -> List[Dict]:
        """
        Discover all temporal patterns in events.
        
        Returns:
            List of temporal patterns
        """
        by_entity = self._group_events_by_entity(events)
        _LOGGER.info(f"Analyzing temporal patterns for {len(by_entity)} entities")
        
        patterns = []
        for entity_id, entity_events in by_entity.items():
            if len(entity_events) < self.min_occurrences:
                continue
            
            patterns.extend(self._analyze_entity_patterns(entity_id, entity_events))
        
        _LOGGER.info(f"Discovered {len(patterns)} temporal patterns")
        return patterns
    
    def _group_events_by_entity(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """Group events by entity, filtering to valid state transitions."""
        by_entity = defaultdict(list)
        
        for event in events:
            # Only analyze state transitions, not continuous sensors
            if event.get("new_state") in self.config.VALID_STATES:
                by_entity[event["entity_id"]].append(event)
        
        return by_entity
    
    def _analyze_entity_patterns(
        self,
        entity_id: str,
        events: List[Dict]
    ) -> List[Dict]:
        """Analyze all temporal patterns for a single entity."""
        patterns = []
        
        # Check for fixed schedule patterns
        schedule_patterns = self._find_schedule_patterns(entity_id, events)
        patterns.extend(schedule_patterns)
        
        # Check for solar-dependent patterns
        solar_patterns = self._find_solar_patterns(entity_id, events)
        patterns.extend(solar_patterns)
        
        return patterns
    
    # ========================================================================
    # Fixed Schedule Pattern Detection
    # ========================================================================
    
    def _find_schedule_patterns(
        self,
        entity_id: str,
        events: List[Dict]
    ) -> List[Dict]:
        """
        Find fixed schedule patterns.
        
        Algorithm:
        1. Group events by state (on vs off)
        2. For each state, extract time-of-day
        3. Cluster times using coefficient of variation
        4. If cluster is tight enough, it's a schedule pattern
        """
        patterns = []
        by_state = self._group_events_by_state(events)
        
        for state, state_events in by_state.items():
            pattern = self._analyze_schedule_for_state(entity_id, state, state_events)
            if pattern:
                patterns.append(pattern)
        
        return patterns
    
    def _group_events_by_state(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """Group events by target state."""
        by_state = defaultdict(list)
        for event in events:
            by_state[event["new_state"]].append(event)
        return by_state
    
    def _analyze_schedule_for_state(
        self,
        entity_id: str,
        state: str,
        events: List[Dict]
    ) -> Optional[Dict]:
        """Analyze schedule pattern for a specific state transition."""
        if len(events) < self.min_occurrences:
            return None
        
        cluster = self._calculate_time_cluster(events)
        
        if not cluster.is_consistent(
            self.time_tolerance,
            self.config.COEFFICIENT_VARIATION_THRESHOLD
        ):
            return None
        
        return self._create_schedule_pattern(entity_id, state, cluster)
    
    def _calculate_time_cluster(self, events: List[Dict]) -> TimeCluster:
        """Calculate time clustering statistics for events."""
        times_of_day = self._extract_times_of_day(events)
        
        mean_time = sum(times_of_day) / len(times_of_day)
        variance = sum((t - mean_time) ** 2 for t in times_of_day) / len(times_of_day)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean_time if mean_time > 0 else float('inf')
        
        return TimeCluster(
            mean_seconds=mean_time,
            std_dev_seconds=std_dev,
            coefficient_variation=cv,
            event_count=len(events)
        )
    
    def _extract_times_of_day(self, events: List[Dict]) -> List[float]:
        """Extract times as seconds since midnight."""
        times = []
        for event in events:
            dt = datetime.fromtimestamp(event["timestamp"])
            seconds = dt.hour * 3600 + dt.minute * 60 + dt.second
            times.append(seconds)
        return times
    
    def _create_schedule_pattern(
        self,
        entity_id: str,
        state: str,
        cluster: TimeCluster
    ) -> Dict:
        """Create a schedule pattern from time cluster data."""
        return {
            "pattern_type": PATTERN_TYPE_TEMPORAL,
            "trigger_conditions": [{
                "type": "time",
                "time": cluster.mean_time_str,
                "tolerance_minutes": cluster.std_dev_minutes
            }],
            "action_target": {
                "entity_id": entity_id,
                "state": state,
                "service": self._infer_service(entity_id, state)
            },
            "confidence": round(1.0 - cluster.coefficient_variation, 3),
            "support": cluster.event_count / self.config.SUPPORT_DIVISOR,
            "pattern_score": round(
                self._calculate_score(cluster.event_count, cluster.coefficient_variation),
                3
            ),
            "occurrence_count": cluster.event_count,
            "typical_time": cluster.mean_time_str,
            "time_std_dev_minutes": cluster.std_dev_minutes
        }
    
    # ========================================================================
    # Solar Pattern Detection
    # ========================================================================
    
    def _find_solar_patterns(
        self,
        entity_id: str,
        events: List[Dict]
    ) -> List[Dict]:
        """
        Find patterns that correlate with sunrise/sunset.
        
        Solar patterns are common for outdoor lighting.
        """
        solar_events = self._filter_solar_events(events)
        if len(solar_events) < self.min_occurrences:
            return []
        
        return self._analyze_solar_correlations(entity_id, solar_events)
    
    def _filter_solar_events(self, events: List[Dict]) -> List[Dict]:
        """Filter to events that have sun position context."""
        return [e for e in events if e.get("sun_position") is not None]
    
    def _analyze_solar_correlations(
        self,
        entity_id: str,
        solar_events: List[Dict]
    ) -> List[Dict]:
        """Analyze correlations between state changes and sun position."""
        patterns = []
        by_sun_state = self._group_by_sun_and_state(solar_events)
        
        for (sun_pos, state), matching_events in by_sun_state.items():
            pattern = self._create_solar_pattern(
                entity_id,
                sun_pos,
                state,
                matching_events,
                solar_events
            )
            if pattern:
                patterns.append(pattern)
        
        return patterns
    
    def _group_by_sun_and_state(
        self,
        events: List[Dict]
    ) -> Dict[Tuple[str, str], List[Dict]]:
        """Group events by sun position and state."""
        by_sun_state = defaultdict(list)
        for event in events:
            key = (event["sun_position"], event["new_state"])
            by_sun_state[key].append(event)
        return by_sun_state
    
    def _create_solar_pattern(
        self,
        entity_id: str,
        sun_position: str,
        state: str,
        matching_events: List[Dict],
        all_solar_events: List[Dict]
    ) -> Optional[Dict]:
        """Create solar pattern if confidence threshold is met."""
        if len(matching_events) < self.min_occurrences:
            return None
        
        confidence = self._calculate_solar_confidence(
            matching_events,
            all_solar_events,
            state
        )
        
        if confidence < self.config.SOLAR_CONFIDENCE_THRESHOLD:
            return None
        
        return {
            "pattern_type": PATTERN_TYPE_TEMPORAL,
            "trigger_conditions": [{
                "type": "sun",
                "sun_position": sun_position
            }],
            "action_target": {
                "entity_id": entity_id,
                "state": state,
                "service": self._infer_service(entity_id, state)
            },
            "confidence": round(confidence, 3),
            "support": len(matching_events) / self.config.SUPPORT_DIVISOR,
            "pattern_score": round(
                self._calculate_score(len(matching_events), 1.0 - confidence),
                3
            ),
            "occurrence_count": len(matching_events)
        }
    
    def _calculate_solar_confidence(
        self,
        matching_events: List[Dict],
        all_solar_events: List[Dict],
        state: str
    ) -> float:
        """Calculate confidence that state correlates with sun position."""
        total_in_state = len([
            e for e in all_solar_events 
            if e["new_state"] == state
        ])
        
        if total_in_state == 0:
            return 0.0
        
        # Confidence = % of times this state happens at this sun position
        return len(matching_events) / total_in_state
    
    # ========================================================================
    # Service Inference
    # ========================================================================
    
    def _infer_service(self, entity_id: str, state: str) -> str:
        """Infer Home Assistant service for achieving a state."""
        domain = entity_id.split('.')[0]
        
        service_map = {
            "light": f"{domain}.turn_{state}",
            "switch": f"{domain}.turn_{state}",
            "lock": f"lock.{state}",
            "cover": self._get_cover_service(state),
        }
        
        return service_map.get(domain, f"{domain}.turn_{state}")
    
    def _get_cover_service(self, state: str) -> str:
        """Get service for cover domain based on state."""
        if state == "open":
            return "cover.open_cover"
        else:
            return "cover.close_cover"
    
    # ========================================================================
    # Scoring
    # ========================================================================
    
    def _calculate_score(self, occurrences: int, variability: float) -> float:
        """
        Calculate pattern score for temporal patterns.
        
        Higher occurrences and lower variability = higher score.
        
        Args:
            occurrences: Number of times pattern occurred
            variability: Measure of timing inconsistency (0-1)
            
        Returns:
            Score from 0 to 1
        """
        occurrence_score = self._normalize_occurrence_score(occurrences)
        consistency_score = 1.0 - variability
        
        return (
            self.config.CONSISTENCY_WEIGHT * consistency_score +
            self.config.OCCURRENCE_WEIGHT * occurrence_score
        )
    
    def _normalize_occurrence_score(self, occurrences: int) -> float:
        """Normalize occurrence count to 0-1 scale, capped at max threshold."""
        return min(
            occurrences / self.config.MAX_OCCURRENCES_FOR_SCORE,
            1.0
        )
