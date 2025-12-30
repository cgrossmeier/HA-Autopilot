# HA Autopilot - Phase 2: Pattern Recognition

## Overview
Phase 2 discovers behavioral patterns from Phase 1 data using association rule learning,
sequential pattern mining, and temporal analysis.

## Installation

1. Ensure Phase 1 is installed and has generated export data
2. Copy this directory to `/config/custom_components/ha_autopilot/`
3. Add to `configuration.yaml`:
   ```yaml
   ha_autopilot:
     export_dir: /config/ha_autopilot/exports
     min_support: 0.10
     min_confidence: 0.75
     mining_enabled: true
   ```
4. Restart Home Assistant

## Services

### ha_autopilot.discover_patterns
Manually trigger pattern discovery
- `days`: Days of history to analyze (default 30)
- `incremental`: Only process new data (default false)

### ha_autopilot.export_patterns
Export patterns to JSON for Claude Code consumption

### ha_autopilot.clear_patterns
Clear all discovered patterns (requires confirm: true)

## Files

- `__init__.py` - Component initialization and service registration
- `const.py` - Configuration constants
- `pattern_storage.py` - Database layer for pattern persistence
- `association_miner.py` - Association rule learning (FP-Growth)
- `sequence_miner.py` - Sequential pattern detection
- `temporal_analyzer.py` - Time-based pattern analysis
- `pattern_validator.py` - Pattern validation and scoring
- `pattern_engine.py` - Main orchestrator
- `manifest.json` - HA component metadata
- `services.yaml` - Service definitions

## Scheduled Execution

Patterns are discovered automatically at 3:00 AM daily.
Check logs for execution status.

## Output

Patterns are stored in Home Assistant database tables:
- `ha_autopilot_patterns` - Discovered patterns
- `ha_autopilot_transactions` - Transaction data for mining
- `ha_autopilot_sequences` - Sequential pattern steps

Export file: `/config/ha_autopilot/exports/patterns_for_review.json`
