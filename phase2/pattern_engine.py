"""
Pattern discovery engine for HA Autopilot.

Orchestrates the complete pattern discovery pipeline:
1. Load Phase 1 data
2. Build transactions
3. Run association mining
4. Run sequence mining
5. Run temporal analysis
6. Validate and score patterns
7. Store in database
8. Export for Claude Code

This is the main entry point for pattern discovery.
"""

import sys
sys.path.insert(0, '/config/ha_autopilot')

import os
import json
import glob
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from exporter import DataExporter
from .association_miner import AssociationMiner
from .sequence_miner import SequenceMiner
from .temporal_analyzer import TemporalAnalyzer
from .pattern_validator import PatternValidator
from .pattern_storage import PatternStorage
from .const import (
    EXPORT_DIR,
    PATTERN_EXPORT_FILE,
    DEFAULT_MIN_SUPPORT,
    DEFAULT_MIN_CONFIDENCE,
)

_LOGGER = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class DiscoveryStats:
    """Statistics from a pattern discovery run."""
    events_loaded: int
    transactions_built: int
    patterns_discovered: int
    patterns_validated: int
    patterns_stored: int
    duration_seconds: float
    
    def to_dict(self) -> Dict:
        return {
            "events_processed": self.events_loaded,
            "transactions_built": self.transactions_built,
            "patterns_discovered": self.patterns_discovered,
            "patterns_validated": self.patterns_validated,
            "patterns_stored": self.patterns_stored,
            "run_duration_seconds": self.duration_seconds,
        }


# ============================================================================
# Pattern Discovery Engine
# ============================================================================

class PatternEngine:
    """
    Main pattern discovery engine.
    
    Coordinates all pattern mining algorithms and manages
    the complete discovery-validation-storage pipeline.
    
    Args:
        hass: Home Assistant instance
        storage: PatternStorage instance
        export_dir: Directory containing Phase 1 exports
        min_support: Minimum support for association rules
        min_confidence: Minimum confidence for association rules
    """
    
    def __init__(
        self,
        hass,
        storage: PatternStorage,
        export_dir: str = "/config/ha_autopilot/exports",
        min_support: float = DEFAULT_MIN_SUPPORT,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE
    ):
        self.hass = hass
        self.storage = storage
        self.export_dir = export_dir
        
        # Initialize mining components
        self.assoc_miner = AssociationMiner(
            min_support=min_support,
            min_confidence=min_confidence
        )
        self.seq_miner = SequenceMiner()
        self.temporal_analyzer = TemporalAnalyzer()
        self.validator = PatternValidator()
        
        _LOGGER.info("Pattern engine initialized")
    
    # ========================================================================
    # Main Discovery Pipeline
    # ========================================================================
    
    def discover_patterns(self, days: int = 30, incremental: bool = False) -> int:
        """
        Run complete pattern discovery pipeline.
        
        Args:
            days: Days of history to analyze
            incremental: If True, only process new data since last run
            
        Returns:
            Number of patterns discovered and stored
        """
        _LOGGER.info(f"Starting pattern discovery (days={days}, incremental={incremental})")
        start_time = datetime.now()
        
        try:
            stats = self._run_discovery_pipeline(days, incremental)
            self._log_completion(stats, start_time)
            return stats.patterns_stored
            
        except Exception as e:
            _LOGGER.error(f"Pattern discovery failed: {e}", exc_info=True)
            return 0
    
    def _run_discovery_pipeline(self, days: int, incremental: bool) -> DiscoveryStats:
        """Execute the complete discovery pipeline and return statistics."""
        start_time = datetime.now()
        
        # Step 1: Load events
        events = self._load_and_validate_events(days)
        
        # Step 2: Build and store transactions
        transactions = self._build_and_store_transactions(events)
        
        # Step 3: Mine patterns from all sources
        all_patterns = self._mine_all_patterns(events, transactions)
        
        # Step 4: Validate and score patterns
        validated_patterns = self._validate_patterns(all_patterns)
        
        # Step 5: Store validated patterns
        stored_count = self._store_patterns(validated_patterns)
        
        # Step 6: Record run metadata
        duration = (datetime.now() - start_time).total_seconds()
        stats = DiscoveryStats(
            events_loaded=len(events),
            transactions_built=len(transactions),
            patterns_discovered=len(all_patterns),
            patterns_validated=len(validated_patterns),
            patterns_stored=stored_count,
            duration_seconds=duration
        )
        
        self._record_run_metadata(stats, days)
        return stats
    
    # ========================================================================
    # Pipeline Steps
    # ========================================================================
    
    def _load_and_validate_events(self, days: int) -> List[Dict]:
        """Load event data and validate it's usable."""
        events = self._load_event_data(days)
        
        if not events:
            _LOGGER.warning("No events loaded, cannot discover patterns")
            raise ValueError("No events available for pattern discovery")
        
        _LOGGER.info(f"Loaded {len(events)} events for analysis")
        return events
    
    def _build_and_store_transactions(self, events: List[Dict]) -> List[Dict]:
        """Build transactions and persist them to storage."""
        _LOGGER.info("Building transactions...")
        trans_meta, trans_items = self.assoc_miner.build_transactions(events)
        
        # Store transactions in database
        for trans in trans_meta:
            self.storage.store_transaction(trans)
        
        _LOGGER.info(f"Built and stored {len(trans_meta)} transactions")
        return trans_items
    
    def _mine_all_patterns(self, events: List[Dict], transactions: List[Dict]) -> List[Dict]:
        """Run all pattern mining algorithms."""
        patterns = []
        
        # Association patterns
        _LOGGER.info("Mining association patterns...")
        assoc_patterns = self.assoc_miner.mine_patterns(transactions)
        patterns.extend(assoc_patterns)
        _LOGGER.info(f"Found {len(assoc_patterns)} association patterns")
        
        # Sequential patterns
        _LOGGER.info("Mining sequential patterns...")
        seq_patterns = self.seq_miner.mine_sequences(events)
        patterns.extend(seq_patterns)
        _LOGGER.info(f"Found {len(seq_patterns)} sequential patterns")
        
        # Temporal patterns
        _LOGGER.info("Analyzing temporal patterns...")
        temp_patterns = self.temporal_analyzer.analyze_temporal_patterns(events)
        patterns.extend(temp_patterns)
        _LOGGER.info(f"Found {len(temp_patterns)} temporal patterns")
        
        _LOGGER.info(f"Total patterns discovered: {len(patterns)}")
        return patterns
    
    def _validate_patterns(self, patterns: List[Dict]) -> List[Dict]:
        """Validate and filter patterns."""
        _LOGGER.info("Validating patterns...")
        validated = self.validator.validate_patterns(patterns)
        _LOGGER.info(f"Patterns after validation: {len(validated)}")
        return validated
    
    def _store_patterns(self, patterns: List[Dict]) -> int:
        """Store validated patterns in database."""
        _LOGGER.info("Storing patterns in database...")
        stored_count = 0
        
        for pattern in patterns:
            pattern_id = self.storage.store_pattern(pattern)
            if pattern_id:
                stored_count += 1
        
        _LOGGER.info(f"Stored {stored_count} patterns")
        return stored_count
    
    # ========================================================================
    # Data Loading
    # ========================================================================
    
    def _load_event_data(self, days: int) -> List[Dict]:
        """
        Load event data from Phase 1 exports.
        
        Looks for the most recent export file and loads events
        within the requested time range.
        
        Args:
            days: Days of history needed
            
        Returns:
            List of event dictionaries
        """
        latest_file = self._find_latest_export_file()
        if not latest_file:
            return []
        
        all_events = self._load_events_from_file(latest_file)
        filtered_events = self._filter_events_by_date(all_events, days)
        
        return filtered_events
    
    def _find_latest_export_file(self) -> Optional[str]:
        """Find the most recent Phase 1 export file."""
        pattern = os.path.join(self.export_dir, "state_changes_*.jsonl")
        export_files = glob.glob(pattern)
        
        if not export_files:
            _LOGGER.error(f"No export files found in {self.export_dir}")
            _LOGGER.error("Run Phase 1 extraction first: python run_extraction.py")
            return None
        
        latest_file = max(export_files, key=os.path.getctime)
        _LOGGER.info(f"Loading events from {os.path.basename(latest_file)}")
        return latest_file
    
    def _load_events_from_file(self, filepath: str) -> List[Dict]:
        """Load all events from a JSONL file."""
        exporter = DataExporter(output_dir=self.export_dir)
        return exporter.load_jsonl(filepath)
    
    def _filter_events_by_date(self, events: List[Dict], days: int) -> List[Dict]:
        """Filter events to the requested time range."""
        cutoff_time = datetime.now() - timedelta(days=days)
        cutoff_ts = cutoff_time.timestamp()
        
        filtered = [
            e for e in events
            if e.get("timestamp", 0) >= cutoff_ts
        ]
        
        _LOGGER.info(f"Filtered to {len(filtered)} events from last {days} days")
        return filtered
    
    # ========================================================================
    # Pattern Export
    # ========================================================================
    
    def export_patterns(self, min_score: float = 0.70) -> str:
        """
        Export patterns for Claude Code consumption.
        
        Creates a JSON file with all patterns that meet the minimum score,
        formatted for Claude Code to generate natural language suggestions.
        
        Args:
            min_score: Minimum pattern score to include
            
        Returns:
            Path to exported file
        """
        patterns = self._fetch_patterns_for_export(min_score)
        export_data = self._format_export_data(patterns, min_score)
        filepath = self._write_export_file(export_data)
        
        _LOGGER.info(f"Exported {len(patterns)} patterns to {filepath}")
        return filepath
    
    def _fetch_patterns_for_export(self, min_score: float) -> List[Dict]:
        """Retrieve patterns that meet export criteria."""
        return self.storage.get_patterns(
            min_score=min_score,
            status="active"
        )
    
    def _format_export_data(self, patterns: List[Dict], min_score: float) -> Dict:
        """Format patterns for Claude Code consumption."""
        export_data = {
            "generated_at": datetime.now().isoformat(),
            "pattern_count": len(patterns),
            "min_score": min_score,
            "patterns": []
        }
        
        for pattern in patterns:
            export_data["patterns"].append({
                "id": pattern["pattern_id"],
                "type": pattern["pattern_type"],
                "trigger": pattern["trigger_conditions"],
                "action": pattern["action_target"],
                "confidence": pattern["confidence"],
                "support": pattern["support"],
                "score": pattern["pattern_score"],
                "occurrences": pattern["occurrence_count"],
                "recommendation": pattern.get("recommendation", "review")
            })
        
        return export_data
    
    def _write_export_file(self, data: Dict) -> str:
        """Write export data to JSON file."""
        os.makedirs(self.export_dir, exist_ok=True)
        filepath = os.path.join(self.export_dir, PATTERN_EXPORT_FILE)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        return filepath
    
    # ========================================================================
    # Metadata and Logging
    # ========================================================================
    
    def _record_run_metadata(self, stats: DiscoveryStats, days: int):
        """Store run metadata for tracking and debugging."""
        metadata = {
            "last_discovery_run": datetime.now().timestamp(),
            "days_analyzed": days,
            **stats.to_dict()
        }
        
        _LOGGER.debug(f"Run metadata: {json.dumps(metadata, indent=2)}")
        # Future: Use pattern_storage to write to metadata table
    
    def _log_completion(self, stats: DiscoveryStats, start_time: datetime):
        """Log discovery completion summary."""
        elapsed = (datetime.now() - start_time).total_seconds()
        _LOGGER.info(
            f"Pattern discovery complete in {elapsed:.1f}s - "
            f"Discovered: {stats.patterns_discovered}, "
            f"Validated: {stats.patterns_validated}, "
            f"Stored: {stats.patterns_stored}"
        )
