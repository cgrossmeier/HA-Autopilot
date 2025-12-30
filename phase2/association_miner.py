"""
Association rule mining for HA Autopilot.

Uses FP-Growth algorithm to discover frequent itemsets,
then generates association rules with confidence metrics.

Theory:
- Itemset: A set of things that occur together {light.living_room:on, person.dad:home}
- Support: How often does this itemset appear?
- Confidence: When antecedent occurs, how often does consequent follow?
- Lift: Is this correlation stronger than random chance?
"""

import sys
sys.path.insert(0, '/config/ha_autopilot')

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
from dataclasses import dataclass

import pandas as pd
from mlxtend.frequent_patterns import fpgrowth, association_rules
from mlxtend.preprocessing import TransactionEncoder

from exporter import DataExporter
from .const import (
    TRANSACTION_WINDOWS,
    DEFAULT_MIN_SUPPORT,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_LIFT,
    DEFAULT_MIN_CONVICTION,
    PATTERN_TYPE_ASSOCIATION,
)

_LOGGER = logging.getLogger(__name__)


# ============================================================================
# Configuration and Thresholds
# ============================================================================

class AssociationConfig:
    """Configuration for association rule mining."""
    
    # Default window size
    DEFAULT_WINDOW_SIZE = TRANSACTION_WINDOWS.get("medium", 900)
    
    # Transaction constraints
    MIN_EVENTS_IN_WINDOW = 2
    MIN_TRANSACTIONS_FOR_MINING = 10
    
    # Window overlap
    WINDOW_OVERLAP_RATIO = 0.5  # 50% overlap
    
    # Scoring weights
    CONFIDENCE_WEIGHT = 0.30
    LIFT_WEIGHT = 0.25
    CONVICTION_WEIGHT = 0.20
    SUPPORT_WEIGHT = 0.15
    SIMPLICITY_WEIGHT = 0.10
    
    # Metric normalization
    LIFT_NORMALIZATION_FACTOR = 5.0
    CONVICTION_NORMALIZATION_FACTOR = 5.0
    
    # Complexity thresholds
    SIMPLE_RULE_TRIGGER_COUNT = 3
    SIMPLE_RULE_BONUS = 1.0
    COMPLEX_RULE_PENALTY = 0.5


@dataclass
class TransactionWindow:
    """Represents a transaction window with metadata."""
    start_ts: float
    end_ts: float
    items: Set[str]
    events: List[Dict]
    
    @property
    def quality_score(self) -> float:
        """Average quality score of events in window."""
        scores = [e.get("quality_score", 1.0) for e in self.events]
        return sum(scores) / len(scores) if scores else 1.0
    
    @property
    def day_type(self) -> str:
        """Day type (weekday/weekend) based on first event."""
        if not self.events:
            return "weekday"
        return "weekend" if self.events[0].get("is_weekend") else "weekday"
    
    @property
    def time_bucket(self) -> Optional[str]:
        """Time bucket from first event."""
        if not self.events:
            return None
        return self.events[0].get("time_bucket")
    
    def to_metadata_dict(self) -> Dict:
        """Convert to metadata dictionary for storage."""
        return {
            "window_start": self.start_ts,
            "window_end": self.end_ts,
            "context_day_type": self.day_type,
            "context_time_bucket": self.time_bucket,
            "items": list(self.items),
            "quality_score": self.quality_score,
            "event_count": len(self.events)
        }


@dataclass
class Item:
    """Represents an item in a transaction (entity:state pair)."""
    entity_id: str
    state: str
    
    def __str__(self) -> str:
        """Format as entity_id:state."""
        return f"{self.entity_id}:{self.state}"
    
    @classmethod
    def from_string(cls, item_str: str) -> 'Item':
        """Parse from entity_id:state format."""
        entity_id, state = item_str.split(':', 1)
        return cls(entity_id=entity_id, state=state)
    
    @classmethod
    def from_event(cls, event: Dict) -> 'Item':
        """Create from event dictionary."""
        return cls(
            entity_id=event["entity_id"],
            state=event["new_state"]
        )


# ============================================================================
# Service Inference
# ============================================================================

class ServiceInferrer:
    """
    Infers Home Assistant services needed to achieve states.
    
    This is heuristic-based. Claude Code will refine this in Phase 3.
    """
    
    @staticmethod
    def infer_service(entity_id: str, state: str) -> str:
        """Infer the service needed to achieve a state."""
        domain = entity_id.split('.')[0]
        
        service_handlers = {
            "light": ServiceInferrer._handle_light,
            "switch": ServiceInferrer._handle_switch,
            "lock": ServiceInferrer._handle_lock,
            "cover": ServiceInferrer._handle_cover,
            "climate": ServiceInferrer._handle_climate,
            "media_player": ServiceInferrer._handle_media_player,
        }
        
        handler = service_handlers.get(domain)
        if handler:
            return handler(domain, state)
        
        # Default fallback
        return f"{domain}.turn_{state}"
    
    @staticmethod
    def _handle_light(domain: str, state: str) -> str:
        """Handle light domain services."""
        if state == "on":
            return "light.turn_on"
        elif state == "off":
            return "light.turn_off"
        elif state.isdigit():  # Brightness level
            return "light.turn_on"
        return f"light.turn_{state}"
    
    @staticmethod
    def _handle_switch(domain: str, state: str) -> str:
        """Handle switch domain services."""
        return f"switch.turn_{state}"
    
    @staticmethod
    def _handle_lock(domain: str, state: str) -> str:
        """Handle lock domain services."""
        return f"lock.{state}"
    
    @staticmethod
    def _handle_cover(domain: str, state: str) -> str:
        """Handle cover domain services."""
        if state in ["open", "opening"]:
            return "cover.open_cover"
        elif state in ["closed", "closing"]:
            return "cover.close_cover"
        return f"cover.{state}"
    
    @staticmethod
    def _handle_climate(domain: str, state: str) -> str:
        """Handle climate domain services."""
        return "climate.set_temperature"
    
    @staticmethod
    def _handle_media_player(domain: str, state: str) -> str:
        """Handle media_player domain services."""
        if state == "playing":
            return "media_player.media_play"
        elif state in ["paused", "idle"]:
            return "media_player.media_pause"
        return f"media_player.{state}"


# ============================================================================
# Association Rule Miner
# ============================================================================

class AssociationMiner:
    """
    Discovers association rules from state change events.
    
    Process:
    1. Build transactions from state change events
    2. Run FP-Growth to find frequent itemsets
    3. Generate association rules
    4. Filter by confidence, lift, conviction
    5. Convert to pattern format for storage
    
    Args:
        min_support: Minimum support threshold (default 0.10)
        min_confidence: Minimum confidence threshold (default 0.75)
        min_lift: Minimum lift threshold (default 1.2)
        min_conviction: Minimum conviction threshold (default 1.5)
    """
    
    def __init__(
        self,
        min_support: float = DEFAULT_MIN_SUPPORT,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        min_lift: float = DEFAULT_MIN_LIFT,
        min_conviction: float = DEFAULT_MIN_CONVICTION
    ):
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_lift = min_lift
        self.min_conviction = min_conviction
        self.config = AssociationConfig()
        self.service_inferrer = ServiceInferrer()
    
    # ========================================================================
    # Transaction Building
    # ========================================================================
    
    def build_transactions(
        self,
        events: List[Dict],
        window_size: int = None
    ) -> Tuple[List[Dict], List[List[str]]]:
        """
        Convert state change events into transactions.
        
        A transaction is a set of entity:state pairs that occurred
        within a time window. We use sliding windows to capture
        relationships between events.
        
        Example:
        Events at 16:00, 16:02, 16:03, 16:15 with 15-minute window:
        - Window 1 (16:00-16:15): {light.living_room:on, person.dad:home}
        - Window 2 (16:02-16:17): {person.dad:home, binary_sensor.door:on}
        
        Args:
            events: List of state change events from Phase 1
            window_size: Window size in seconds (default 900 = 15 minutes)
            
        Returns:
            Tuple of (transaction_metadata, transaction_itemsets)
            - metadata: List of dicts with context about each transaction
            - itemsets: List of lists, each containing "entity:state" strings
        """
        if not events:
            return [], []
        
        if window_size is None:
            window_size = self.config.DEFAULT_WINDOW_SIZE
        
        sorted_events = sorted(events, key=lambda e: e["timestamp"])
        windows = self._create_sliding_windows(sorted_events, window_size)
        
        transactions_meta = [w.to_metadata_dict() for w in windows]
        transactions_items = [list(w.items) for w in windows]
        
        _LOGGER.info(
            f"Built {len(transactions_items)} transactions from {len(events)} events"
        )
        
        return transactions_meta, transactions_items
    
    def _create_sliding_windows(
        self,
        events: List[Dict],
        window_size: int
    ) -> List[TransactionWindow]:
        """Create sliding windows from sorted events."""
        windows = []
        i = 0
        
        while i < len(events):
            window = self._create_window_at_position(events, i, window_size)
            
            if window and len(window.events) >= self.config.MIN_EVENTS_IN_WINDOW:
                windows.append(window)
            
            # Slide window forward by overlap ratio
            i += max(1, int(len(window.events) * self.config.WINDOW_OVERLAP_RATIO))
        
        return windows
    
    def _create_window_at_position(
        self,
        events: List[Dict],
        start_idx: int,
        window_size: int
    ) -> Optional[TransactionWindow]:
        """Create a transaction window starting at specific index."""
        window_start_ts = events[start_idx]["timestamp"]
        window_end_ts = window_start_ts + window_size
        
        # Collect events in this window
        window_events = []
        j = start_idx
        
        while j < len(events) and events[j]["timestamp"] < window_end_ts:
            window_events.append(events[j])
            j += 1
        
        if len(window_events) < self.config.MIN_EVENTS_IN_WINDOW:
            return None
        
        # Build itemset
        items = {str(Item.from_event(event)) for event in window_events}
        
        return TransactionWindow(
            start_ts=window_start_ts,
            end_ts=window_end_ts,
            items=items,
            events=window_events
        )
    
    # ========================================================================
    # Pattern Mining
    # ========================================================================
    
    def mine_patterns(
        self,
        transactions: List[List[str]],
        context_filter: str = None
    ) -> List[Dict]:
        """
        Run FP-Growth and generate association rules.
        
        FP-Growth Algorithm:
        1. Count frequency of each item
        2. Build FP-tree (compressed representation)
        3. Mine tree for frequent itemsets
        4. Generate rules from itemsets
        
        Args:
            transactions: List of itemset lists
            context_filter: Optional context (e.g., "weekday_evening")
            
        Returns:
            List of discovered patterns
        """
        if not self._validate_transactions(transactions):
            return []
        
        _LOGGER.info(f"Mining patterns from {len(transactions)} transactions")
        
        # Convert to binary matrix
        df = self._prepare_transaction_matrix(transactions)
        if df is None:
            return []
        
        # Find frequent itemsets
        frequent_itemsets = self._find_frequent_itemsets(df)
        if frequent_itemsets is None or len(frequent_itemsets) == 0:
            return []
        
        # Generate association rules
        rules = self._generate_association_rules(frequent_itemsets)
        if rules is None or len(rules) == 0:
            return []
        
        # Filter rules by metrics
        filtered_rules = self._filter_rules(rules)
        _LOGGER.info(f"After filtering: {len(filtered_rules)} rules remain")
        
        # Convert to pattern format
        patterns = self._convert_rules_to_patterns(filtered_rules, context_filter)
        return patterns
    
    def _validate_transactions(self, transactions: List[List[str]]) -> bool:
        """Validate that we have enough transactions for mining."""
        if len(transactions) < self.config.MIN_TRANSACTIONS_FOR_MINING:
            _LOGGER.warning(
                f"Only {len(transactions)} transactions, "
                f"need at least {self.config.MIN_TRANSACTIONS_FOR_MINING} "
                f"for meaningful patterns"
            )
            return False
        return True
    
    def _prepare_transaction_matrix(
        self,
        transactions: List[List[str]]
    ) -> Optional[pd.DataFrame]:
        """Convert transactions to binary matrix format for mlxtend."""
        try:
            te = TransactionEncoder()
            te_ary = te.fit(transactions).transform(transactions)
            return pd.DataFrame(te_ary, columns=te.columns_)
        except Exception as e:
            _LOGGER.error(f"Transaction encoding failed: {e}")
            return None
    
    def _find_frequent_itemsets(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Run FP-Growth to find frequent itemsets."""
        try:
            frequent_itemsets = fpgrowth(
                df,
                min_support=self.min_support,
                use_colnames=True
            )
            
            if len(frequent_itemsets) == 0:
                _LOGGER.warning("No frequent itemsets found, try lowering min_support")
                return None
            
            _LOGGER.info(f"Found {len(frequent_itemsets)} frequent itemsets")
            return frequent_itemsets
            
        except Exception as e:
            _LOGGER.error(f"FP-Growth failed: {e}")
            return None
    
    def _generate_association_rules(
        self,
        frequent_itemsets: pd.DataFrame
    ) -> Optional[pd.DataFrame]:
        """Generate association rules from frequent itemsets."""
        try:
            rules = association_rules(
                frequent_itemsets,
                metric="confidence",
                min_threshold=self.min_confidence
            )
            
            if len(rules) == 0:
                _LOGGER.warning("No rules meet confidence threshold")
                return None
            
            _LOGGER.info(f"Generated {len(rules)} association rules")
            return rules
            
        except Exception as e:
            _LOGGER.error(f"Rule generation failed: {e}")
            return None
    
    def _filter_rules(self, rules: pd.DataFrame) -> pd.DataFrame:
        """Filter rules by lift and conviction thresholds."""
        return rules[
            (rules['lift'] >= self.min_lift) &
            (rules['conviction'] >= self.min_conviction)
        ]
    
    # ========================================================================
    # Rule Conversion
    # ========================================================================
    
    def _convert_rules_to_patterns(
        self,
        rules: pd.DataFrame,
        context: str = None
    ) -> List[Dict]:
        """Convert filtered rules to pattern format."""
        patterns = []
        
        for _, rule in rules.iterrows():
            pattern = self._rule_to_pattern(rule, context)
            if pattern:
                patterns.append(pattern)
        
        return patterns
    
    def _rule_to_pattern(
        self,
        rule,
        context: str = None
    ) -> Optional[Dict]:
        """
        Convert mlxtend rule to our pattern format.
        
        Rule structure:
        - antecedents: frozenset of items that trigger
        - consequents: frozenset of items that result
        - support: frequency of the full itemset
        - confidence: P(consequent | antecedent)
        - lift: confidence / P(consequent)
        - conviction: (1 - P(consequent)) / (1 - confidence)
        
        Pattern format:
        - trigger_conditions: List of {entity_id, state, context}
        - action_target: {entity_id, state, service}
        - Statistical metrics
        """
        # Parse antecedents (triggers)
        triggers = self._parse_antecedents(rule['antecedents'], context)
        
        # Parse consequents (actions) - only single-action patterns for now
        action = self._parse_consequent(rule['consequents'])
        if action is None:
            return None
        
        # Calculate pattern score
        pattern_score = self._calculate_pattern_score(rule, len(triggers))
        
        # Calculate approximate occurrence count
        occurrence_count = self._estimate_occurrences(rule)
        
        return {
            "pattern_type": PATTERN_TYPE_ASSOCIATION,
            "trigger_conditions": triggers,
            "action_target": action,
            "confidence": round(rule['confidence'], 3),
            "support": round(rule['support'], 3),
            "lift": round(rule['lift'], 3),
            "conviction": round(rule['conviction'], 3),
            "pattern_score": round(pattern_score, 3),
            "occurrence_count": occurrence_count
        }
    
    def _parse_antecedents(
        self,
        antecedents: frozenset,
        context: str = None
    ) -> List[Dict]:
        """Parse antecedents into trigger conditions."""
        triggers = []
        
        for item_str in antecedents:
            item = Item.from_string(item_str)
            triggers.append({
                "entity_id": item.entity_id,
                "state": item.state,
                "context": context
            })
        
        return triggers
    
    def _parse_consequent(self, consequents: frozenset) -> Optional[Dict]:
        """Parse consequents into action target."""
        # For association rules, focus on single-action patterns
        if len(consequents) != 1:
            # Multi-consequent rules are complex, skip for now
            return None
        
        consequent_str = list(consequents)[0]
        item = Item.from_string(consequent_str)
        
        service = self.service_inferrer.infer_service(item.entity_id, item.state)
        
        return {
            "entity_id": item.entity_id,
            "state": item.state,
            "service": service
        }
    
    # ========================================================================
    # Scoring
    # ========================================================================
    
    def _calculate_pattern_score(self, rule, trigger_count: int) -> float:
        """
        Calculate composite pattern score.
        
        Weighted combination of metrics:
        - Confidence: How reliably does consequent follow?
        - Lift: How much stronger than random chance?
        - Conviction: How dependent is consequent on antecedent?
        - Support: How frequently does this occur?
        - Simplicity: Prefer rules with fewer triggers
        """
        confidence_score = rule['confidence']
        lift_score = self._normalize_lift(rule['lift'])
        conviction_score = self._normalize_conviction(rule['conviction'])
        support_score = rule['support']
        simplicity_score = self._calculate_simplicity_score(trigger_count)
        
        return (
            self.config.CONFIDENCE_WEIGHT * confidence_score +
            self.config.LIFT_WEIGHT * lift_score +
            self.config.CONVICTION_WEIGHT * conviction_score +
            self.config.SUPPORT_WEIGHT * support_score +
            self.config.SIMPLICITY_WEIGHT * simplicity_score
        )
    
    def _normalize_lift(self, lift: float) -> float:
        """Normalize lift to 0-1 scale."""
        return min(lift / self.config.LIFT_NORMALIZATION_FACTOR, 1.0)
    
    def _normalize_conviction(self, conviction: float) -> float:
        """Normalize conviction to 0-1 scale."""
        return min(conviction / self.config.CONVICTION_NORMALIZATION_FACTOR, 1.0)
    
    def _calculate_simplicity_score(self, trigger_count: int) -> float:
        """Calculate score bonus for simple rules."""
        if trigger_count <= self.config.SIMPLE_RULE_TRIGGER_COUNT:
            return self.config.SIMPLE_RULE_BONUS
        else:
            return self.config.COMPLEX_RULE_PENALTY
    
    def _estimate_occurrences(self, rule) -> int:
        """Estimate occurrence count from support."""
        # Approximate based on support
        # This is a rough estimate; actual count would need transaction tracking
        return int(rule['support'] * 100)
