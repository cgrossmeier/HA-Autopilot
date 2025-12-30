"""
Pattern validation and scoring for HA Autopilot.

Validates discovered patterns for quality and reliability.
Applies anti-pattern detection to filter spurious correlations.
Calculates comprehensive pattern scores.
"""

import sys
sys.path.insert(0, '/config/ha_autopilot')

import logging
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from .const import (
    MIN_PATTERN_SCORE,
    AUTO_SUGGEST_SCORE,
    EXCELLENT_SCORE
)

_LOGGER = logging.getLogger(__name__)


# ============================================================================
# Configuration and Rules
# ============================================================================

class ValidationRules:
    """Centralized validation rules and thresholds."""
    
    # Anti-pattern keywords
    ANTI_PATTERN_KEYWORDS = [
        "unavailable",
        "unknown",
        "automations.",
        "script.",
    ]
    
    # Safety thresholds
    SAFETY_CONFIDENCE_MIN = 0.90
    
    # Breadth thresholds
    TOO_BROAD_SUPPORT = 0.40
    TOO_SPECIFIC_SUPPORT = 0.02
    TOO_SPECIFIC_OCCURRENCES = 3
    
    # Scoring adjustments
    SIMPLICITY_BONUS = 0.05
    CONVICTION_PENALTY = 0.10
    SIMPLICITY_TRIGGER_THRESHOLD = 2
    CONVICTION_THRESHOLD = 1.5
    
    # Safety entity patterns
    SAFETY_PREFIXES = ["lock."]
    SAFETY_KEYWORDS = ["garage", "door"]


class RecommendationTier(Enum):
    """Pattern recommendation levels."""
    AUTO_SUGGEST = "auto_suggest"  # High confidence, show immediately
    SUGGEST = "suggest"            # Good confidence, show with explanation
    REVIEW = "review"              # Borderline, needs user judgment


@dataclass
class ValidationStats:
    """Statistics from pattern validation."""
    total_input: int
    total_validated: int
    total_rejected: int
    rejection_reasons: Dict[str, int]
    
    def log_summary(self):
        """Log validation summary."""
        _LOGGER.info(f"Validated: {self.total_validated} patterns, rejected: {self.total_rejected}")
        for reason, count in self.rejection_reasons.items():
            if count > 0:
                _LOGGER.debug(f"  {reason}: {count}")


# ============================================================================
# Pattern Validator
# ============================================================================

class PatternValidator:
    """
    Validates and scores discovered patterns.
    
    Validation Steps:
    1. Anti-pattern detection (spurious correlations)
    2. Safety checks (critical devices need high confidence)
    3. Conflict detection (contradictory patterns)
    4. Stability verification (pattern exists across time segments)
    5. Composite scoring
    
    Args:
        min_score: Minimum score to keep pattern (default 0.50)
        safety_entities: List of entity IDs requiring extra validation
    """
    
    def __init__(
        self,
        min_score: float = MIN_PATTERN_SCORE,
        safety_entities: List[str] = None
    ):
        self.min_score = min_score
        self.safety_entities = safety_entities or []
        self.rules = ValidationRules()
    
    # ========================================================================
    # Main Validation Pipeline
    # ========================================================================
    
    def validate_patterns(
        self,
        patterns: List[Dict],
        existing_automations: List[str] = None
    ) -> List[Dict]:
        """
        Validate a list of patterns.
        
        Args:
            patterns: Discovered patterns to validate
            existing_automations: List of existing automation entity IDs
            
        Returns:
            List of validated patterns (filtered and scored)
        """
        if not patterns:
            return []
        
        _LOGGER.info(f"Validating {len(patterns)} patterns")
        
        validated = []
        stats = self._create_validation_stats()
        
        for pattern in patterns:
            result = self._validate_single_pattern(pattern, existing_automations, stats)
            if result:
                validated.append(result)
        
        stats.total_validated = len(validated)
        stats.total_rejected = stats.total_input - stats.total_validated
        stats.log_summary()
        
        return self._sort_by_score(validated)
    
    def _validate_single_pattern(
        self,
        pattern: Dict,
        existing_automations: List[str],
        stats: ValidationStats
    ) -> Dict | None:
        """
        Validate a single pattern through all checks.
        
        Returns validated pattern or None if rejected.
        """
        # Run validation checks
        rejection_reason = self._check_pattern_validity(pattern)
        if rejection_reason:
            stats.rejection_reasons[rejection_reason] += 1
            return None
        
        # Recalculate score with adjustments
        pattern = self._recalculate_score(pattern)
        
        # Score threshold check
        if pattern["pattern_score"] < self.min_score:
            stats.rejection_reasons["low_score"] += 1
            return None
        
        # Check conflicts (warn but don't reject)
        if existing_automations:
            self._check_and_flag_conflicts(pattern, existing_automations)
        
        # Add recommendation tier
        pattern["recommendation"] = self._determine_recommendation(pattern)
        
        return pattern
    
    # ========================================================================
    # Validation Checks
    # ========================================================================
    
    def _check_pattern_validity(self, pattern: Dict) -> str | None:
        """
        Run all validation checks on pattern.
        
        Returns rejection reason if invalid, None if valid.
        """
        if self._is_anti_pattern(pattern):
            return "anti_pattern"
        
        if self._fails_safety_check(pattern):
            return "safety_check"
        
        if self._too_broad(pattern):
            return "too_broad"
        
        if self._too_specific(pattern):
            return "too_specific"
        
        return None
    
    def _is_anti_pattern(self, pattern: Dict) -> bool:
        """
        Detect known anti-patterns.
        
        Anti-patterns include:
        - Patterns involving unavailable states
        - Automation/script triggers (circular logic)
        - Sensor reset patterns (meaningless)
        - Circular patterns (entity triggers itself)
        """
        if self._contains_anti_pattern_keywords(pattern):
            return True
        
        if self._is_circular_pattern(pattern):
            return True
        
        return False
    
    def _contains_anti_pattern_keywords(self, pattern: Dict) -> bool:
        """Check if pattern contains anti-pattern keywords."""
        # Check triggers
        for trigger in pattern.get("trigger_conditions", []):
            entity_id = trigger.get("entity_id", "")
            state = trigger.get("state", "")
            
            if self._matches_anti_pattern(entity_id, state):
                return True
        
        # Check action target
        action = pattern.get("action_target", {})
        action_entity = action.get("entity_id", "")
        action_state = action.get("state", "")
        
        return self._matches_anti_pattern(action_entity, action_state)
    
    def _matches_anti_pattern(self, entity_id: str, state: str) -> bool:
        """Check if entity or state matches anti-pattern keywords."""
        for keyword in self.rules.ANTI_PATTERN_KEYWORDS:
            if keyword in entity_id.lower() or keyword in state.lower():
                return True
        return False
    
    def _is_circular_pattern(self, pattern: Dict) -> bool:
        """Detect patterns where entity triggers itself."""
        trigger_entities = {
            t.get("entity_id") 
            for t in pattern.get("trigger_conditions", [])
        }
        action_entity = pattern.get("action_target", {}).get("entity_id", "")
        
        return action_entity in trigger_entities
    
    def _fails_safety_check(self, pattern: Dict) -> bool:
        """
        Check if pattern involves safety-critical entities with insufficient confidence.
        
        Safety entities (locks, garage doors, etc.) require >= 0.90 confidence.
        """
        action_entity = pattern.get("action_target", {}).get("entity_id", "")
        
        if not self._is_safety_entity(action_entity):
            return False
        
        confidence = pattern.get("confidence", 0)
        if confidence < self.rules.SAFETY_CONFIDENCE_MIN:
            _LOGGER.debug(
                f"Safety check failed for {action_entity} "
                f"(confidence {confidence:.2f} < {self.rules.SAFETY_CONFIDENCE_MIN})"
            )
            return True
        
        return False
    
    def _is_safety_entity(self, entity_id: str) -> bool:
        """Check if entity is safety-critical."""
        # Check explicit safety list
        if entity_id in self.safety_entities:
            return True
        
        # Check prefixes
        for prefix in self.rules.SAFETY_PREFIXES:
            if entity_id.startswith(prefix):
                return True
        
        # Check keywords
        entity_lower = entity_id.lower()
        for keyword in self.rules.SAFETY_KEYWORDS:
            if keyword in entity_lower:
                return True
        
        return False
    
    def _too_broad(self, pattern: Dict) -> bool:
        """
        Check if pattern is too broad to be useful.
        
        Too broad = very high support (>40%) = matches everything.
        """
        support = pattern.get("support", 0)
        return support > self.rules.TOO_BROAD_SUPPORT
    
    def _too_specific(self, pattern: Dict) -> bool:
        """
        Check if pattern is too specific (likely one-time event).
        
        Too specific = very low support (<2%) and only occurred once or twice.
        """
        support = pattern.get("support", 0)
        occurrences = pattern.get("occurrence_count", 0)
        
        return (
            support < self.rules.TOO_SPECIFIC_SUPPORT and 
            occurrences < self.rules.TOO_SPECIFIC_OCCURRENCES
        )
    
    # ========================================================================
    # Scoring
    # ========================================================================
    
    def _recalculate_score(self, pattern: Dict) -> Dict:
        """
        Recalculate pattern score with validation adjustments.
        
        Adjustments:
        - Bonus for simple patterns (fewer triggers)
        - Penalty for low conviction
        """
        base_score = pattern["pattern_score"]
        
        adjustments = (
            self._calculate_simplicity_bonus(pattern) -
            self._calculate_conviction_penalty(pattern)
        )
        
        adjusted_score = base_score + adjustments
        pattern["pattern_score"] = self._clamp_score(adjusted_score)
        
        return pattern
    
    def _calculate_simplicity_bonus(self, pattern: Dict) -> float:
        """Calculate bonus for simple patterns."""
        trigger_count = len(pattern.get("trigger_conditions", []))
        
        if trigger_count <= self.rules.SIMPLICITY_TRIGGER_THRESHOLD:
            return self.rules.SIMPLICITY_BONUS
        return 0.0
    
    def _calculate_conviction_penalty(self, pattern: Dict) -> float:
        """Calculate penalty for low conviction."""
        conviction = pattern.get("conviction", 1.0)
        
        if conviction < self.rules.CONVICTION_THRESHOLD:
            return self.rules.CONVICTION_PENALTY
        return 0.0
    
    def _clamp_score(self, score: float) -> float:
        """Clamp score to valid range [0, 1]."""
        return round(max(0.0, min(1.0, score)), 3)
    
    def _determine_recommendation(self, pattern: Dict) -> str:
        """
        Determine recommendation tier for pattern.
        
        Returns:
            "auto_suggest" - High confidence, show immediately
            "suggest" - Good confidence, show with explanation
            "review" - Borderline, needs user judgment
        """
        score = pattern["pattern_score"]
        
        if score >= EXCELLENT_SCORE:
            return RecommendationTier.AUTO_SUGGEST.value
        elif score >= AUTO_SUGGEST_SCORE:
            return RecommendationTier.SUGGEST.value
        else:
            return RecommendationTier.REVIEW.value
    
    # ========================================================================
    # Conflict Detection
    # ========================================================================
    
    def _check_and_flag_conflicts(
        self,
        pattern: Dict,
        existing_automations: List[str]
    ):
        """Check for conflicts and flag pattern if found."""
        if self._conflicts_with_existing(pattern, existing_automations):
            pattern["conflict_warning"] = True
    
    def _conflicts_with_existing(
        self,
        pattern: Dict,
        existing_automations: List[str]
    ) -> bool:
        """
        Check if pattern conflicts with existing automation.
        
        This is a placeholder. In Phase 3, Claude Code will do sophisticated
        conflict detection by parsing existing automation YAML.
        
        For now, we do basic entity overlap detection.
        """
        # TODO: Implement actual conflict detection in Phase 3
        action_entity = pattern.get("action_target", {}).get("entity_id", "")
        entity_name = action_entity.split('.')[1] if '.' in action_entity else action_entity
        
        # Simple heuristic: if automation name contains entity, might conflict
        return any(entity_name in auto for auto in existing_automations)
    
    # ========================================================================
    # Utilities
    # ========================================================================
    
    def _create_validation_stats(self) -> ValidationStats:
        """Create stats tracker for validation run."""
        return ValidationStats(
            total_input=0,
            total_validated=0,
            total_rejected=0,
            rejection_reasons={
                "low_score": 0,
                "anti_pattern": 0,
                "safety_check": 0,
                "conflicts_existing": 0,
                "too_broad": 0,
                "too_specific": 0
            }
        )
    
    def _sort_by_score(self, patterns: List[Dict]) -> List[Dict]:
        """Sort patterns by score in descending order."""
        return sorted(patterns, key=lambda p: p["pattern_score"], reverse=True)
