# HA-Autopilot Implementation Guide

**Complete Documentation for Phases 1 & 2**

**System Version**: HA-Autopilot v2.0
**Home Assistant Version**: 2025.12.5
**Implementation Date**: December 29-30, 2025

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Phase 1: Data Pipeline](#phase-1-data-pipeline)
4. [Phase 2: Pattern Recognition](#phase-2-pattern-recognition)
5. [Installation](#installation)
6. [Configuration](#configuration)
7. [Usage Examples](#usage-examples)
8. [Code Structure](#code-structure)
9. [Algorithms](#algorithms)
10. [Troubleshooting](#troubleshooting)

---

## System Overview

### What is HA-Autopilot?

HA-Autopilot is a two-phase system that automatically discovers automation opportunities in your Home Assistant installation by analyzing historical state changes and detecting statistically significant patterns.

**Phase 1**: Data Pipeline
- Extracts state change history from Home Assistant database
- Filters noise and enriches with contextual information
- Exports clean, structured data for analysis

**Phase 2**: Pattern Recognition
- Analyzes state changes for temporal, sequential, and conditional patterns
- Calculates statistical confidence using Wilson score intervals
- Generates Home Assistant automation YAML configurations

### Key Features

✅ **Fully Automated Pattern Detection**
- No manual data labeling required
- Statistical confidence guarantees (90%+ default)
- Handles 30-90 days of historical data

✅ **Three Pattern Types**
- Temporal: Time-based routines (e.g., "lights on at 6 PM")
- Sequential: Event sequences (e.g., "TV on → lights dim")
- Conditional: Multi-condition rules (e.g., "after sunset AND home")

✅ **Safe Automation Generation**
- Automatic backups before installation
- Duplicate prevention
- Clear labeling (`[Autopilot]` prefix)
- Manual review workflow

✅ **Production-Ready**
- Tested on real Home Assistant installation
- 3,229 events analyzed from 30 days
- 2,824 patterns detected
- 145 automations generated

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                  HA-AUTOPILOT SYSTEM                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │             PHASE 1: DATA PIPELINE              │    │
│  ├────────────────────────────────────────────────┤    │
│  │                                                  │    │
│  │  1. Database Connector (SQLite/MariaDB)        │    │
│  │  2. Entity Classifier (High/Medium/Low Signal) │    │
│  │  3. State Change Extractor (LAG window)        │    │
│  │  4. Context Builder (Temporal + Environmental)  │    │
│  │  5. Noise Filter (Flapping detection)          │    │
│  │  6. Data Exporter (JSONL format)               │    │
│  │                                                  │    │
│  │  Output: 3,229 events from 189 entities        │    │
│  └────────────────────────────────────────────────┘    │
│                          ↓                              │
│  ┌────────────────────────────────────────────────┐    │
│  │          PHASE 2: PATTERN RECOGNITION           │    │
│  ├────────────────────────────────────────────────┤    │
│  │                                                  │    │
│  │  1. Temporal Analyzer (Time-based patterns)     │    │
│  │  2. Sequential Analyzer (A→B sequences)        │    │
│  │  3. Conditional Analyzer (If-then rules)        │    │
│  │  4. Automation Generator (YAML output)          │    │
│  │  5. Backup System (Safety)                      │    │
│  │  6. Report Generator (Documentation)            │    │
│  │                                                  │    │
│  │  Output: 2,824 patterns, 145 automations       │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
Home Assistant Database (SQLite/MariaDB)
    ↓
[Phase 1] Extract & Filter State Changes
    ↓
JSONL Export (26.5 MB for 30 days)
    ↓
[Phase 2] Analyze Patterns with Statistical Confidence
    ↓
Automation Suggestions (YAML)
    ↓
Manual Review → Install → Reload in HA
```

---

## Phase 1: Data Pipeline

### Purpose

Transform raw Home Assistant state history into clean, enriched datasets suitable for pattern analysis.

### Implementation

**File**: `run_extraction.py`

**Process**:
1. Connect to database (smart fallback: MariaDB → SQLite)
2. Classify entities by signal quality (high/medium/low)
3. Extract state changes using window functions
4. Enrich with temporal and environmental context
5. Filter noise and detect flapping
6. Export to JSONL format with metadata

### Entity Classification

**High-Signal Entities** (175 detected):
- Binary sensors (doors, windows, motion, presence, occupancy)
- Lights (30+ zones)
- Switches (lighting control, automation toggles)
- Covers (motorized blinds)
- Person entities

**Medium-Signal Entities** (14 detected):
- Climate controls (Ecobee thermostats)
- Vacuums (Roborock)

**Excluded** (896 entities):
- Weather sensors (constant updates)
- Sun position (predictable)
- Device trackers (handled separately)
- Low-activity sensors (< 5 events)

### Context Enrichment

Each event includes:
- **Temporal**: hour, minute, day_of_week, is_weekend, time_bucket
- **States**: old_state, new_state, seconds_since_last_change
- **Environment**: sun_position, people_home, anyone_home
- **Concurrent**: other entity states within ±60 seconds
- **Quality**: quality_score, during_flap flag

### Database Query

Uses LAG window function for efficient state change extraction:

```sql
WITH state_sequence AS (
    SELECT
        entity_id,
        state,
        last_updated_ts,
        LAG(state) OVER (
            PARTITION BY entity_id
            ORDER BY last_updated_ts
        ) as prev_state
    FROM states
    WHERE last_updated_ts BETWEEN :start AND :end
)
SELECT *
FROM state_sequence
WHERE state != prev_state OR prev_state IS NULL
```

### Performance

- **7 days**: 6 seconds, 1,972 events, 15.8 MB
- **30 days**: 11 seconds, 3,229 events, 26.5 MB
- **Throughput**: ~300 events/second

---

## Phase 2: Pattern Recognition

### Purpose

Automatically discover automation opportunities by detecting statistically significant patterns in state change history.

### Implementation Files

1. `temporal_analyzer.py` - Time-based pattern detection
2. `sequential_analyzer.py` - Event sequence detection
3. `conditional_analyzer.py` - Multi-condition pattern detection
4. `automation_generator.py` - YAML automation generation
5. `run_pattern_detection.py` - Main orchestration script

### Pattern Types

#### 1. Temporal Patterns

**Definition**: Events that occur at consistent times of day/week.

**Detection Method**:
- Group events by entity, hour, and day-of-week
- Calculate occurrence rate vs opportunities
- Compute Wilson score confidence intervals
- Identify daily, weekday, weekend, and specific-day patterns

**Examples**:
```
Light.Office → 'on' at 09:00 on weekdays
(95% confidence, 20 occurrences)

Cover.Blinds → 'closed' at 20:30 every day
(92% confidence, 28 occurrences)
```

**Algorithm**:
```python
def analyze_temporal_pattern(entity_events, total_days):
    # Group by hour
    for hour in 0..23:
        events_at_hour = filter(events, hour=hour)

        # Check daily pattern
        confidence = wilson_score(
            successes=len(events_at_hour),
            trials=total_days
        )

        if confidence >= threshold:
            create_pattern(entity, hour, 'daily', confidence)
```

#### 2. Sequential Patterns

**Definition**: Event B consistently follows event A within a time window.

**Detection Method**:
- Track time delays between potential trigger and action events
- Calculate average delay and consistency
- Use sliding window (default: 5 minutes)
- Compute confidence for A→B relationship

**Examples**:
```
Media_Player.TV → 'on' ⟹ Light.Living_Room → 'off'
(within 60s, avg 15s, 92% confidence, 18× )

Binary_Sensor.Door → 'on' ⟹ Light.Hallway → 'on'
(within 30s, avg 5s, 88% confidence, 25× )
```

**Algorithm**:
```python
def analyze_sequential_pattern(trigger_events, all_events, window=300):
    for trigger_event in trigger_events:
        trigger_time = trigger_event.timestamp

        # Find events within window
        for other_event in all_events:
            delay = other_event.timestamp - trigger_time

            if 0 < delay <= window:
                record_sequence(trigger_event, other_event, delay)

    # Calculate confidence
    for (trigger, action), delays in sequences:
        confidence = wilson_score(
            successes=len(delays),
            trials=len(trigger_events)
        )
```

#### 3. Conditional Patterns

**Definition**: Events that occur under specific conditions.

**Detection Method**:
- Analyze concurrent states during each event
- Identify time-of-day correlations
- Detect presence-based patterns
- Calculate conditional probability

**Examples**:
```
When after 6 PM AND someone home ⟹ Light.Porch → 'on'
(95% confidence, 30× )

When office occupied AND weekday ⟹ Climate.Office → 'heat_cool'
(88% confidence, 45× )
```

**Algorithm**:
```python
def analyze_conditional_pattern(events):
    for event in events:
        # Check time conditions
        if event.hour >= 18:  # After 6 PM
            record_condition(event, 'time', 'after_6pm')

        # Check presence conditions
        if event.anyone_home:
            record_condition(event, 'presence', 'someone_home')

        # Check concurrent states
        for entity, state in event.concurrent_states:
            record_condition(event, 'state', (entity, state))

    # Calculate conditional confidence
    for (action, condition), occurrences in patterns:
        confidence = wilson_score(
            successes=occurrences,
            trials=total_action_occurrences
        )
```

---

## Algorithms

### Wilson Score Confidence Interval

**Purpose**: Calculate conservative confidence estimate for pattern reliability.

**Why Wilson Score?**
- More accurate than simple proportion for small samples
- Provides 95% confidence interval
- Returns lower bound (conservative estimate)
- Handles edge cases (0% and 100% success rates)

**Formula**:
```
Given:
  p = successes / trials
  z = 1.96  (95% confidence level)

Calculate:
  denominator = 1 + z²/trials
  center = (p + z²/(2×trials)) / denominator
  margin = (z/denominator) × √(p×(1-p)/trials + z²/(4×trials²))

Confidence = center - margin  (lower bound)
```

**Implementation**:
```python
def wilson_score(successes: int, trials: int) -> float:
    """Calculate Wilson score confidence interval lower bound"""
    if trials == 0:
        return 0.0

    p = successes / trials

    # Edge cases
    if p == 1.0:
        return max(0.0, 1.0 - (2.0 / trials))
    if p == 0.0:
        return 0.0

    z = 1.96  # 95% confidence
    denominator = 1 + z**2 / trials
    center = (p + z**2 / (2*trials)) / denominator
    sqrt_term = max(0.0, p*(1-p)/trials + z**2/(4*trials**2))
    margin = (z / denominator) * math.sqrt(sqrt_term)

    return max(0.0, min(1.0, center - margin))
```

**Example**:
```
Pattern: Light turns on at 9 AM on 18 out of 20 weekdays

Simple proportion: 18/20 = 90%
Wilson score (95% CI): 68.3% - 98.2%
Lower bound (conservative): 68.3%

This means we're 95% confident the true rate is at least 68.3%.
```

---

## Installation

### Prerequisites

- Home Assistant OS (any version)
- Python 3.11+ with venv
- SQLite3 (included in HA OS)
- At least 30 days of Home Assistant history

### Setup Steps

1. **Create Project Directory**:
```bash
mkdir -p /config/ha_autopilot
cd /config/ha_autopilot
```

2. **Create Virtual Environment**:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install Dependencies**:
```bash
pip install PyYAML
```

4. **Copy Phase 1 Files**:
- `database.py`
- `entity_classifier.py`
- `extractor.py`
- `context_builder.py`
- `noise_filter.py`
- `exporter.py`
- `run_extraction.py`

5. **Copy Phase 2 Files**:
- `temporal_analyzer.py`
- `sequential_analyzer.py`
- `conditional_analyzer.py`
- `automation_generator.py`
- `run_pattern_detection.py`

6. **Make Scripts Executable**:
```bash
chmod +x run_extraction.py run_pattern_detection.py
```

---

## Configuration

### Phase 1 Configuration

**Database Connection**:
No configuration needed - automatically detects SQLite database at `/config/home-assistant_v2.db`.

For MariaDB (optional):
```python
# In database.py
MARIADB_CONFIG = {
    'host': 'YOUR_MARIADB_HOST',
    'user': 'YOUR_MARIADB_USER',
    'password': 'YOUR_MARIADB_PASSWORD',
    'database': 'homeassistant'
}
```

**Entity Filtering**:
```python
# In entity_classifier.py
EXCLUDED_DOMAINS = ['weather', 'sun', 'automation', 'script']
MIN_EVENTS_FOR_CLASSIFICATION = 5
```

### Phase 2 Configuration

**Confidence Threshold**:
```bash
# Command line (recommended)
python run_pattern_detection.py --confidence 0.90

# Or edit run_pattern_detection.py
min_confidence = 0.90  # 90% minimum confidence
```

**Pattern Detection Parameters**:
```python
# In temporal_analyzer.py
TemporalAnalyzer(
    min_confidence=0.90,
    min_occurrences=5
)

# In sequential_analyzer.py
SequentialAnalyzer(
    min_confidence=0.90,
    min_occurrences=5,
    max_window=300  # 5 minutes
)
```

**Excluded Entities**:
```python
# In automation_generator.py
self.excluded_entities = {
    'climate.thermostat_main',
    'climate.thermostat_upstairs',
    # Add entities to exclude from automation
}
```

---

## Usage Examples

### Example 1: Initial Setup and Pattern Discovery

```bash
# Step 1: Extract 30 days of data
cd /config/ha_autopilot
source venv/bin/activate
python run_extraction.py --days 30

# Step 2: Run pattern detection (no install)
python run_pattern_detection.py --no-install

# Step 3: Review results
cat suggestions/pattern_report_*.md
cat suggestions/automations_*.yaml

# Step 4: Install selected automations manually
# Edit /config/automations.yaml and copy desired automations

# Step 5: Reload in Home Assistant UI
# Settings → Automations → ⋮ → Reload Automations
```

### Example 2: Conservative Pattern Detection

```bash
# Use 95% confidence threshold (very conservative)
python run_pattern_detection.py --confidence 0.95 --no-install

# Review only the highest-confidence patterns
```

### Example 3: Automatic Installation with Backup

```bash
# Let system install automations automatically
python run_pattern_detection.py

# Backup is created automatically at:
# /config/ha_autopilot/backups/automations_backup_*.yaml

# Reload automations in HA UI to activate
```

### Example 4: Iterative Refinement

```bash
# Start conservative
python run_pattern_detection.py --confidence 0.95 --no-install

# Review and install manually, then try lower threshold
python run_pattern_detection.py --confidence 0.85 --no-install

# Compare results and choose best patterns
```

---

## Code Structure

### Phase 1 Modules

**database.py**
- Database connection management
- Smart fallback (MariaDB → SQLite)
- Connection pooling and error handling

**entity_classifier.py**
- Entity classification (high/medium/low signal)
- Domain-based filtering
- Activity-based scoring

**extractor.py**
- State change extraction with LAG window
- Timestamp filtering
- Result batching

**context_builder.py**
- Temporal context (hour, day, weekend)
- Environmental context (sun position, presence)
- Concurrent state tracking

**noise_filter.py**
- Flapping detection (rapid state changes)
- Quality scoring
- Low-activity filtering

**exporter.py**
- JSONL export format
- Metadata generation
- Entity statistics

**run_extraction.py**
- Main pipeline orchestration
- Command-line interface
- Progress reporting

### Phase 2 Modules

**temporal_analyzer.py**
- Time-based pattern detection
- Day-of-week analysis
- Confidence calculation

**sequential_analyzer.py**
- Event sequence detection
- Time window analysis
- Delay tracking

**conditional_analyzer.py**
- Multi-condition pattern detection
- Correlation analysis
- Presence/time/state conditions

**automation_generator.py**
- YAML automation generation
- Service mapping (domain.state → domain.service)
- Safety exclusions

**run_pattern_detection.py**
- Pipeline orchestration
- Backup management
- Report generation

---

## Troubleshooting

### Common Issues

#### Issue: "No patterns detected"

**Symptoms**: Analysis completes but finds 0 patterns

**Causes**:
- Insufficient data (less than 30 days)
- Very high confidence threshold (95%+)
- Low activity in monitored period
- Irregular schedules (no consistent patterns)

**Solutions**:
1. Gather more data: Run Phase 1 for 60-90 days
2. Lower threshold: `--confidence 0.75`
3. Check Phase 1 export: Verify entity_count > 0
4. Review raw data: `cat exports/export_metadata.json`

#### Issue: "Patterns seem incorrect"

**Symptoms**: Detected patterns don't match expected behavior

**Causes**:
- Correlations vs causations (refrigerator opens when home = correlation)
- Unusual activity during data period (guests, renovations)
- Binary sensor patterns (observational, not actionable)
- Small sample size

**Solutions**:
1. Focus on controllable entities (lights, switches, covers)
2. Ignore binary sensor patterns (they're observational)
3. Review pattern confidence and occurrence counts
4. Gather data during normal routine periods

#### Issue: "Automations not appearing in HA"

**Symptoms**: Automations installed but not visible in UI

**Causes**:
- Automations not reloaded
- YAML syntax errors
- File permissions issues

**Solutions**:
1. Reload automations: Settings → Automations → ⋮ → Reload
2. Check YAML syntax: Settings → System → Configuration Validation
3. Review logs: `/config/home-assistant.log`
4. Check file permissions: `ls -l /config/automations.yaml`

#### Issue: "Too many automations generated"

**Symptoms**: 100+ automations created

**Causes**:
- Low confidence threshold
- Many controllable entities
- High activity level

**Solutions**:
1. Increase threshold: `--confidence 0.95`
2. Manual selection: Review and install selectively
3. Use `--dry-run` first to preview count
4. Adjust min_occurrences in analyzer code

---

## Performance Optimization

### Memory Usage

**Phase 1**:
- Loads events in chunks (no full table scan)
- Typical memory: 50-100 MB for 30 days

**Phase 2**:
- Loads all events into memory for analysis
- Typical memory: 100-200 MB for 30 days

**For Large Datasets (90+ days)**:
```python
# In run_extraction.py
CHUNK_SIZE = 10000  # Process in smaller chunks

# In run_pattern_detection.py
# Run multiple analyses with different date ranges
# Then merge results
```

### Execution Time

**Phase 1** (30 days):
- Database query: 5-8 seconds
- Processing: 2-3 seconds
- Export: 1 second
- **Total**: ~11 seconds

**Phase 2** (3,229 events):
- Temporal analysis: ~5 seconds
- Sequential analysis: ~8 seconds
- Conditional analysis: ~12 seconds
- Automation generation: < 1 second
- **Total**: ~28 seconds

### Storage Requirements

**Phase 1 Exports**:
- 7 days: 15.8 MB
- 30 days: 26.5 MB
- 90 days: ~80 MB (estimated)

**Phase 2 Output**:
- Automations YAML: < 100 KB
- Pattern report: < 500 KB
- Backups: Same as automations.yaml

---

## Security Considerations

### Sensitive Data

**Phase 1** exports contain:
- Entity IDs and states (can reveal home layout)
- Timestamps (can reveal schedules)
- No credentials or access tokens

**Recommendations**:
- Keep exports in `/config/ha_autopilot/` (not publicly accessible)
- Don't share JSONL exports publicly
- Backups contain automation IDs but no credentials

### Database Access

**SQLite**:
- Read-only access
- Local file access only
- No network exposure

**MariaDB** (if used):
- Credentials in code (consider environment variables)
- Network access required
- Use read-only database user

### Automation Safety

**Generated automations**:
- Never control locks or security systems (excluded)
- Climate controls excluded by default
- All automations clearly labeled
- Backup system prevents data loss

---

## Advanced Topics

### Custom Pattern Types

**Add new pattern detector**:
1. Create new analyzer file (e.g., `duration_analyzer.py`)
2. Implement pattern detection logic
3. Add to `run_pattern_detection.py` pipeline
4. Update automation generator for new pattern type

### Integration with Node-RED

**Export patterns for Node-RED**:
```python
# In automation_generator.py
def generate_node_red_json(patterns):
    # Convert patterns to Node-RED flow format
    ...
```

### Scheduled Automation

**Run pattern detection daily**:
```yaml
# In automations.yaml
- alias: "Daily Pattern Detection"
  trigger:
    - platform: time
      at: "03:00:00"
  action:
    - service: shell_command.run_pattern_detection

# In configuration.yaml
shell_command:
  run_pattern_detection: >
    cd /config/ha_autopilot &&
    source venv/bin/activate &&
    python run_pattern_detection.py --no-install >> logs/pattern_detection.log 2>&1
```

---

## Credits and License

**HA-Autopilot System**
- Developed for Home Assistant 2025.12.5
- Uses Wilson score confidence intervals
- SQLite/MariaDB support
- JSONL data format

**Dependencies**:
- Python 3.11+
- PyYAML 6.0+
- SQLite3 (built-in)

**License**: Implementation-specific (customize as needed)

---

## Appendix: Sample Output

### Sample Pattern Report

```markdown
# Pattern Detection Report

Generated: 2025-12-30 15:51:27
Confidence Threshold: 90%

## Summary

- Total Patterns Detected: 2824
  - Temporal: 140
  - Sequential: 5
  - Conditional: 2679
- Automations Generated: 145

## Top Temporal Patterns

1. Refrigerator Door → 'on' at 09:09 every day (100% confidence, 30×)
2. Kitchen Door → 'on' at 12:11 every day (100% confidence, 17×)
3. Office Light → 'on' at 09:00 on weekdays (95% confidence, 20×)
...
```

### Sample Automation

```yaml
- id: autopilot_temporal_20251230_abc123
  alias: '[Autopilot] Light Office at 09:00 weekday'
  description: 'Auto-generated from pattern detection. 95% confidence based on 20 occurrences.'
  triggers:
    - trigger: time
      at: "09:00:00"
  conditions:
    - condition: time
      weekday: [mon, tue, wed, thu, fri]
  actions:
    - action: light.turn_on
      target:
        entity_id: light.office
  mode: single
```

---

*End of Implementation Guide*

*For support and troubleshooting, refer to PHASE2_COMPLETE.md and PHASE2_README.md*
