# HA Autopilot - Phase 1: Data Pipeline

## Overview
Phase 1 extracts meaningful state change history from Home Assistant's recorder database,
enriches it with context, filters noise, and exports clean datasets for pattern recognition.

## Installation

1. Copy all files to `/config/ha_autopilot/`
2. Create virtual environment:
   ```bash
   cd /config/ha_autopilot
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Test connection:
   ```bash
   python test_connection.py
   ```

4. Run extraction:
   ```bash
   python run_extraction.py --days 30
   ```

## Files

- `database.py` - Database connection with SQLite/MariaDB fallback
- `entity_classifier.py` - Entity signal quality filtering  
- `extractor.py` - State change extraction with LAG window
- `context_builder.py` - Context vector construction
- `noise_filter.py` - Quality scoring and flapping detection
- `exporter.py` - JSON Lines export
- `run_extraction.py` - Main pipeline orchestrator
- `test_*.py` - Testing utilities
- `explore_data.py` - Data visualization

## Output

Phase 1 generates:
- `/config/ha_autopilot/exports/state_changes_YYYYMMDD_HHMMSS.jsonl` - Event data
- `/config/ha_autopilot/exports/export_metadata.json` - Statistics

These files are consumed by Phase 2 for pattern recognition.
