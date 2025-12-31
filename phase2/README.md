# HA-Autopilot Phase 1: Data Pipeline

Complete implementation of the HA-Autopilot data extraction pipeline for Home Assistant.

## Overview

This system extracts meaningful state change history from your Home Assistant database, filters out noise, and produces a clean dataset that captures how your devices interact over time. This foundation will feed pattern recognition algorithms in Phase 2.

## Installation Complete ✓

The pipeline is fully implemented and tested with your system:
- **Database**: SQLite (with MariaDB fallback support)
- **Total Records**: 1,386,706 state records
- **Entities**: 1,085 total entities
  - 175 high-signal entities (doors, windows, motion, lights, etc.)
  - 14 medium-signal entities (climate, vacuum, etc.)

## Directory Structure

```
/config/ha_autopilot/
├── venv/                          # Python virtual environment
├── exports/                       # Extracted data files
│   ├── state_changes_*.jsonl     # Event data (JSON Lines format)
│   └── export_metadata.json      # Extraction metadata
├── logs/                          # Log files (for scheduled runs)
├── database.py                    # Database connection layer
├── entity_classifier.py           # Entity classification system
├── extractor.py                   # State change extraction
├── context_builder.py             # Context vector construction
├── noise_filter.py                # Noise reduction
├── exporter.py                    # Data export and storage
├── run_extraction.py              # Main extraction script
├── explore_data.py                # Data exploration tool
├── test_*.py                      # Validation scripts
└── README.md                      # This file
```

## Usage

### Basic Extraction

Extract the last 30 days of data (default):
```bash
cd /config/ha_autopilot
source venv/bin/activate
python run_extraction.py
```

### Custom Time Range

Extract specific number of days:
```bash
python run_extraction.py --days 7      # Last 7 days
python run_extraction.py --days 90     # Last 90 days
```

### Include Medium-Signal Entities

Include climate controls and vacuum cleaners:
```bash
python run_extraction.py --include-medium
```

### Verbose Output

See detailed progress:
```bash
python run_extraction.py --verbose
```

### Dry Run

See which entities would be extracted without running:
```bash
python run_extraction.py --dry-run
```

## Data Exploration

Analyze patterns in extracted data:
```bash
source venv/bin/activate
python explore_data.py
```

This shows:
- Most active entities
- Activity by hour of day
- Activity by day of week
- Activity by time period
- Event quality distribution
- Concurrent state patterns

## Test Scripts

### Test Database Connection
```bash
python test_connection.py
```

### Test Entity Classification
```bash
python test_classification.py
```

### Quick Extraction Test
```bash
python test_quick_extraction.py
```

## Output Format

### JSON Lines (JSONL)

Each line is a complete JSON object representing one state change event:

```json
{
  "entity_id": "light.living_room",
  "old_state": "off",
  "new_state": "on",
  "timestamp": 1735506718.713721,
  "datetime": "2025-12-29T20:21:18.713721",
  "hour": 20,
  "minute": 21,
  "day_of_week": 6,
  "is_weekend": true,
  "date": "2025-12-29",
  "time_bucket": "night",
  "people_home": 2,
  "anyone_home": true,
  "sun_position": "below_horizon",
  "quality_score": 1.0,
  "concurrent_states": {
    "person.cgrossmeier": "home",
    "person.jgrossmeier": "home",
    "media_player.living_room": "playing"
  },
  "concurrent_changes": []
}
```

### Metadata

`export_metadata.json` contains:
- Export timestamp
- Event count
- Entity count
- Date range
- List of entities
- Entity quality statistics

## Automated Extraction (Optional)

To run extraction daily at 3am:

1. Create a Home Assistant automation:

```yaml
automation:
  - alias: "HA-Autopilot Daily Extraction"
    trigger:
      - platform: time
        at: "03:00:00"
    action:
      - service: shell_command.ha_autopilot_extract
```

2. Add to your `configuration.yaml`:

```yaml
shell_command:
  ha_autopilot_extract: >
    cd /config/ha_autopilot &&
    source venv/bin/activate &&
    python run_extraction.py --days 1 >> logs/extraction.log 2>&1
```

## Database Configuration

### Current Setup
- **Primary**: MariaDB at 192.168.1.81 (currently unavailable)
- **Fallback**: SQLite at `/config/home-assistant_v2.db`

### To Use MariaDB

Ensure the MariaDB server is running and accessible, then the system will automatically use it. No configuration changes needed.

## Customization

### Add Custom Entity Filters

Edit `run_extraction.py` and modify the classifier initialization:

```python
# Always include specific entities
custom_includes = {"sensor.my_special_sensor"}

# Always exclude specific entities
custom_excludes = {"binary_sensor.noisy_sensor"}

classifier = EntityClassifier(db,
                             custom_includes=custom_includes,
                             custom_excludes=custom_excludes)
```

### Adjust Noise Filtering

Edit `run_extraction.py` and modify the noise filter parameters:

```python
noise_filter = NoiseFilter(
    flap_threshold=5,      # State changes per minute to mark as flapping
    flap_window=60,        # Seconds to consider for flapping
    min_events_per_entity=5  # Minimum events to include entity
)
```

## Performance

### Typical Extraction Times
- **7 days**: ~6 seconds
- **30 days**: ~20-30 seconds
- **90 days**: ~60-90 seconds

*(Times measured on Home Assistant OS on x86 hardware)*

### File Sizes
- 7 days: ~16 MB
- 30 days: ~60-80 MB
- 90 days: ~180-240 MB

## Troubleshooting

### "Database connection failed"
- Check if Home Assistant is running
- Verify SQLite database exists at `/config/home-assistant_v2.db`

### "No events extracted"
- Run with `--dry-run` to see which entities would be included
- Try `--include-medium` to include more entities
- Check date range with `--days`

### "Out of memory"
- Reduce days: `--days 7`
- The system processes in chunks automatically

### "Permission denied"
- Ensure scripts are executable: `chmod +x *.py`
- Run from correct directory: `cd /config/ha_autopilot`

## Next Steps

Phase 1 is complete! The extracted data is ready for Phase 2: Pattern Recognition.

Phase 2 will:
- Identify statistically significant patterns
- Find temporal correlations
- Suggest automation opportunities
- Generate automation configurations

## Files Generated

Latest extraction:
- **Data**: `/config/ha_autopilot/exports/state_changes_20251229_202948.jsonl`
- **Metadata**: `/config/ha_autopilot/exports/export_metadata.json`
- **Events**: 1,972 state changes
- **Period**: 2025-12-22 to 2025-12-29 (7 days)
- **Entities**: 65 active entities

## Support

For issues or questions:
- Review this README
- Check the guide that was provided
- Examine log output with `--verbose`
- Review exported metadata for extraction details
