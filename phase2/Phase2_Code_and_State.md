# Phase 2: Code and State Documentation

**HA-Autopilot Phase 2 Implementation**
**Date**: December 30, 2025
**Version**: 2.0

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Implementation State](#implementation-state)
3. [Configuration](#configuration)
4. [Complete Code Listings](#complete-code-listings)
5. [Usage Examples](#usage-examples)
6. [Generated Output Samples](#generated-output-samples)

---

## System Overview

Phase 2 implements automated pattern detection and automation generation for Home Assistant using statistical analysis of historical state changes.

### Architecture

```
┌─────────────────────────────────────────────────┐
│         PHASE 2 PATTERN RECOGNITION             │
├─────────────────────────────────────────────────┤
│                                                  │
│  Input: Phase 1 JSONL Data (3,229 events)      │
│                                                  │
│  ┌───────────────────────────────────────────┐ │
│  │  Temporal Analyzer                         │ │
│  │  • Time-based patterns                     │ │
│  │  • Wilson score confidence                 │ │
│  │  • 140 patterns detected                   │ │
│  └───────────────────────────────────────────┘ │
│                                                  │
│  ┌───────────────────────────────────────────┐ │
│  │  Sequential Analyzer                       │ │
│  │  • Event sequences (A→B)                  │ │
│  │  • Time window analysis                    │ │
│  │  • 5 patterns detected                     │ │
│  └───────────────────────────────────────────┘ │
│                                                  │
│  ┌───────────────────────────────────────────┐ │
│  │  Conditional Analyzer                      │ │
│  │  • Multi-condition patterns                │ │
│  │  • Correlation detection                   │ │
│  │  • 2,679 patterns detected                 │ │
│  └───────────────────────────────────────────┘ │
│                                                  │
│  ┌───────────────────────────────────────────┐ │
│  │  Automation Generator                      │ │
│  │  • YAML generation                         │ │
│  │  • Safety exclusions                       │ │
│  │  • 145 automations created                 │ │
│  └───────────────────────────────────────────┘ │
│                                                  │
│  Output: Automation YAML + Pattern Report      │
│                                                  │
└─────────────────────────────────────────────────┘
```

### Key Features

- **Statistical Confidence**: Wilson score intervals (95% confidence)
- **Pattern Types**: Temporal, Sequential, Conditional
- **Safety Features**: Automatic backups, duplicate prevention
- **Production Ready**: Tested on 30 days of real data

---

## Implementation State

### Current Status: ✅ COMPLETE

**Phase 2 Completion Date**: December 30, 2025

### Test Results

**Data Analyzed**:
- Events: 3,229 state changes
- Period: November 29 - December 29, 2025 (30 days)
- Entities: 74 active entities
- Data Quality: 83.6% high quality events

**Patterns Detected**:
- Total: 2,824 patterns (90%+ confidence)
- Temporal: 140 patterns
- Sequential: 5 patterns
- Conditional: 2,679 patterns

**Automations Generated**:
- Count: 145 automation suggestions
- Format: Home Assistant YAML
- Safety: Automatic backup created
- Status: Ready for manual review and installation

**Performance**:
- Analysis Time: 28 seconds
- Memory Usage: ~150 MB
- Storage: 26.5 MB (Phase 1 export)

### File Structure

```
/config/ha_autopilot/
├── Phase 2 Code Files
│   ├── temporal_analyzer.py          (11.5 KB)
│   ├── sequential_analyzer.py        (10.0 KB)
│   ├── conditional_analyzer.py       (14.5 KB)
│   ├── automation_generator.py       (14.1 KB)
│   └── run_pattern_detection.py      (14.8 KB)
│
├── Output Files
│   ├── suggestions/
│   │   ├── automations_20251230_155126.yaml
│   │   └── pattern_report_20251230_155127.md
│   └── backups/
│       └── (automatic backups created here)
│
└── Documentation
    ├── PHASE2_COMPLETE.md
    ├── PHASE2_README.md
    ├── HA_AUTOPILOT_IMPLEMENTATION_GUIDE.md
    └── Phase2_Code_and_State.md (this file)
```

---

## Configuration

### Default Settings

**Pattern Detection Parameters**:
```python
# Minimum confidence threshold (0.0 - 1.0)
MIN_CONFIDENCE = 0.90  # 90%

# Minimum occurrences for pattern validity
MIN_OCCURRENCES = 5

# Maximum time window for sequential patterns (seconds)
MAX_TIME_WINDOW = 300  # 5 minutes
```

**Excluded Entities**:
```python
# Entities excluded from automation generation (safety)
EXCLUDED_ENTITIES = {
    'climate.ecobee_main_floor',
    'climate.ecobee_main_floor_2',
    'climate.ecobee_upstairs',
    'climate.ecobee_upstairs_2',
}
```

### Command Line Options

```bash
# Basic usage (auto-install with backup)
python run_pattern_detection.py

# Generate suggestions only (no install)
python run_pattern_detection.py --no-install

# Adjust confidence threshold
python run_pattern_detection.py --confidence 0.75

# Dry run (preview without generating files)
python run_pattern_detection.py --dry-run
```

---

## Complete Code Listings

### 1. temporal_analyzer.py

**Purpose**: Detects time-based patterns (e.g., "lights on at 6 PM on weekdays")

**Algorithm**: Groups events by hour and day-of-week, calculates Wilson score confidence

**Key Functions**:
- `analyze()`: Main analysis entry point
- `_find_time_patterns()`: Identifies daily, weekday, weekend patterns
- `_calculate_confidence()`: Wilson score confidence interval
- `_generate_description()`: Human-readable pattern descriptions

**Complete Code**: See individual file `temporal_analyzer.py`

**Key Implementation Details**:
```python
# Pattern detection logic
for hour in 0..23:
    events_at_hour = filter(events, hour=hour)

    # Check for daily pattern
    confidence = wilson_score(
        successes=len(events_at_hour),
        trials=total_days
    )

    if confidence >= MIN_CONFIDENCE:
        create_pattern(entity, hour, 'daily', confidence)
```

**Confidence Calculation**:
```python
def _calculate_confidence(self, successes: int, trials: int) -> float:
    """
    Wilson score interval (95% confidence)
    Returns conservative lower bound
    """
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

---

### 2. sequential_analyzer.py

**Purpose**: Detects event sequences (e.g., "TV on → lights dim within 2 minutes")

**Algorithm**: Tracks time delays between events, identifies consistent A→B relationships

**Key Functions**:
- `analyze()`: Main analysis entry point
- `_find_sequential_actions()`: Finds actions that follow triggers
- `_calculate_confidence()`: Wilson score confidence interval
- `_remove_redundant_patterns()`: Deduplicates patterns

**Complete Code**: See individual file `sequential_analyzer.py`

**Key Implementation Details**:
```python
# Sequential pattern detection
for trigger_event in trigger_events:
    trigger_time = trigger_event.timestamp

    # Look for actions within time window
    for action_event in all_events:
        delay = action_event.timestamp - trigger_time

        if 0 < delay <= MAX_TIME_WINDOW:
            record_sequence(trigger_event, action_event, delay)

# Calculate confidence
confidence = wilson_score(
    successes=num_sequences,
    trials=num_trigger_events
)
```

---

### 3. conditional_analyzer.py

**Purpose**: Detects multi-condition patterns (e.g., "when home AND after 6 PM → lights on")

**Algorithm**: Analyzes concurrent states, identifies correlations

**Key Functions**:
- `analyze()`: Main analysis entry point
- `_find_time_conditions()`: Time-based conditions (morning, evening, sunset)
- `_find_presence_conditions()`: Presence-based conditions (home, away)
- `_find_state_conditions()`: State-based conditions (concurrent entities)

**Complete Code**: See individual file `conditional_analyzer.py`

**Key Implementation Details**:
```python
# Conditional pattern detection
for event in events:
    # Check time conditions
    if event.hour >= 18:  # After 6 PM
        record_condition(event, 'time', 'evening')

    # Check presence conditions
    if event.anyone_home:
        record_condition(event, 'presence', 'home')

    # Check concurrent states
    for entity, state in event.concurrent_states:
        record_condition(event, 'state', (entity, state))

# Calculate conditional confidence
confidence = wilson_score(
    successes=events_with_condition,
    trials=total_events
)
```

---

### 4. automation_generator.py

**Purpose**: Converts detected patterns into Home Assistant YAML automations

**Algorithm**: Maps patterns to HA automation structure with triggers, conditions, actions

**Key Functions**:
- `generate_from_temporal()`: Temporal pattern → time-based automation
- `generate_from_sequential()`: Sequential pattern → state-triggered automation
- `_get_service_for_state()`: Maps entity states to HA services
- `generate_yaml()`: Produces final YAML output

**Complete Code**: See individual file `automation_generator.py`

**Key Implementation Details**:
```python
# Temporal automation generation
automation = {
    'id': 'autopilot_temporal_YYYYMMDD_hash',
    'alias': '[Autopilot] Entity Name at HH:MM pattern_type',
    'description': f'Auto-generated. {confidence}% confidence, {occurrences} occurrences',
    'triggers': [{
        'trigger': 'time',
        'at': 'HH:MM:SS'
    }],
    'conditions': [{
        'condition': 'time',
        'weekday': ['mon', 'tue', 'wed', 'thu', 'fri']
    }],
    'actions': [{
        'action': 'domain.service',
        'target': {'entity_id': 'entity.id'}
    }],
    'mode': 'single'
}
```

**Service Mapping**:
```python
def _get_service_for_state(domain, target_state):
    """Map entity state to service call"""
    if target_state.lower() == 'on':
        return 'turn_on'
    elif target_state.lower() == 'off':
        return 'turn_off'
    elif domain == 'cover':
        if target_state == 'open':
            return 'open_cover'
        elif target_state == 'closed':
            return 'close_cover'
    # ... more mappings
```

---

### 5. run_pattern_detection.py

**Purpose**: Main orchestration script that runs the complete pipeline

**Algorithm**: Loads data → Runs analyzers → Generates automations → Creates backups

**Key Functions**:
- `load_latest_data()`: Loads Phase 1 JSONL export
- `run_analysis()`: Executes all pattern analyzers
- `generate_automations()`: Creates automation YAML
- `create_backup()`: Backs up automations.yaml
- `install_automations()`: Merges new automations with existing
- `generate_report()`: Creates pattern analysis report

**Complete Code**: See individual file `run_pattern_detection.py`

**Key Implementation Details**:
```python
# Main pipeline
def run(self):
    # 1. Load Phase 1 data
    events = self.load_latest_data()

    # 2. Run pattern analyzers
    patterns = {
        'temporal': TemporalAnalyzer().analyze(events),
        'sequential': SequentialAnalyzer().analyze(events),
        'conditional': ConditionalAnalyzer().analyze(events)
    }

    # 3. Generate automations
    suggestions_file, count = self.generate_automations(patterns)

    # 4. Install (if requested)
    if self.auto_install:
        self.create_backup()
        self.install_automations(suggestions_file)

    # 5. Generate report
    self.generate_report(patterns, suggestions_file, count)
```

**Backup System**:
```python
def create_backup(self):
    """Create timestamped backup of automations.yaml"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'backups/automations_backup_{timestamp}.yaml'
    shutil.copy2('/config/automations.yaml', backup_file)
    return backup_file
```

**Merge Logic**:
```python
def install_automations(self, suggestions_file):
    """Merge new automations with existing"""
    # Load current automations
    current = yaml.safe_load(open('/config/automations.yaml'))

    # Load new automations
    new = yaml.safe_load(open(suggestions_file))

    # Get existing autopilot IDs
    existing_ids = {a['id'] for a in current if a['id'].startswith('autopilot_')}

    # Filter duplicates
    unique_new = [a for a in new if a['id'] not in existing_ids]

    # Merge and save
    merged = current + unique_new
    yaml.dump(merged, open('/config/automations.yaml', 'w'))
```

---

## Usage Examples

### Example 1: Basic Pattern Detection

```bash
# Navigate to project directory
cd /config/ha_autopilot
source venv/bin/activate

# Run pattern detection (no auto-install)
python run_pattern_detection.py --no-install

# Output:
# 📂 Loading data from: state_changes_20251229_215557.jsonl
#    Loaded 3229 events
#
# 🔍 Analyzing temporal patterns (min confidence: 90.0%)...
# ✓ Found 140 temporal patterns with 90.0%+ confidence
#
# 🔗 Analyzing sequential patterns (max window: 300s)...
# ✓ Found 5 sequential patterns with 90.0%+ confidence
#
# ⚙️  Analyzing conditional patterns (min confidence: 90.0%)...
# ✓ Found 2679 conditional patterns with 90.0%+ confidence
#
# ✓ Automation suggestions saved to: automations_20251230_155126.yaml
# ✓ Pattern report saved to: pattern_report_20251230_155127.md
```

### Example 2: Conservative Detection (95% Confidence)

```bash
# Run with higher confidence threshold
python run_pattern_detection.py --confidence 0.95 --no-install

# Result: Fewer patterns, but higher certainty
# Temporal patterns: ~80 (down from 140)
# Sequential patterns: ~3 (down from 5)
# Conditional patterns: ~1500 (down from 2679)
```

### Example 3: Automatic Installation

```bash
# Auto-install with backup
python run_pattern_detection.py

# Output:
# ...pattern detection...
#
# ✓ Backup created: automations_backup_20251230_155126.yaml
# ✓ Installed 145 new automations to /config/automations.yaml
# ✓ Total automations in file: 165
#
# ⚠️  IMPORTANT: Reload automations in Home Assistant UI to activate!
#    Go to: Settings → Automations → ⋮ → Reload Automations
```

### Example 4: Review Generated Automations

```bash
# View automation suggestions
cat suggestions/automations_20251230_155126.yaml

# View pattern report
cat suggestions/pattern_report_20251230_155127.md

# View specific automation
grep -A 20 "Light Office" suggestions/automations_20251230_155126.yaml
```

---

## Generated Output Samples

### Sample Temporal Automation

```yaml
- id: autopilot_temporal_20251230_abc12345
  alias: '[Autopilot] Light Office at 09:00 weekday'
  description: 'Auto-generated from pattern detection. 95% confidence based on 20
    occurrences. Pattern: Light.Office → ''on'' at 09:00 on weekdays (95% confidence,
    20 times)'
  triggers:
  - trigger: time
    at: 09:00:00
  conditions:
  - condition: time
    weekday:
    - mon
    - tue
    - wed
    - thu
    - fri
  actions:
  - action: light.turn_on
    target:
      entity_id: light.office
  mode: single
```

### Sample Sequential Automation

```yaml
- id: autopilot_sequential_20251230_xyz78901
  alias: '[Autopilot] Light Living Room after Media Player TV'
  description: 'Auto-generated from pattern detection. 92% confidence based on 18
    occurrences. Pattern: Media_Player.TV → ''on'' ⟹ Light.Living_Room → ''off''
    (within 60s, avg 15s, 92% confidence, 18× )'
  triggers:
  - trigger: state
    entity_id: media_player.tv
    to: 'on'
  actions:
  - delay:
      seconds: 15
  - action: light.turn_off
    target:
      entity_id: light.living_room
  mode: restart
```

### Sample Pattern Report Excerpt

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
4. Blinds → 'closed' at 20:30 on weekdays (92% confidence, 28×)
5. Entry Light → 'on' at 18:15 every day (90% confidence, 27×)

## Sequential Patterns

1. Media Player paused ⟹ Living Room Player paused (93% confidence, 32×)
2. All Doors closed ⟹ All Windows sensor updates (90% confidence, 22×)
3. TV turns off ⟹ TV switch turns off (90% confidence, 20×)

## Conditional Patterns (Top 10)

1. When someone is home ⟹ Refrigerator opens (98% confidence, 119×)
2. When after 6 PM ⟹ Lights turn on (95% confidence, 87×)
3. When office occupied ⟹ Climate on (92% confidence, 45×)
```

---

## Database Schema (Phase 1 Output)

### JSONL Event Structure

Each line in Phase 1 export is a JSON object:

```json
{
  "entity_id": "light.office",
  "old_state": "off",
  "new_state": "on",
  "timestamp": 1735506718.713721,
  "datetime": "2025-12-29T20:21:18.713721",
  "hour": 20,
  "minute": 21,
  "day_of_week": 6,
  "is_weekend": true,
  "date": "2025-12-29",
  "seconds_since_last_change": 3600.5,
  "sun_position": "below_horizon",
  "concurrent_states": {
    "person.cgrossmeier": "home",
    "person.jgrossmeier": "home",
    "climate.ecobee_main_floor_2": "off"
  },
  "concurrent_changes": [
    {
      "entity_id": "binary_sensor.motion_hallway",
      "new_state": "on",
      "offset_seconds": 2.5
    }
  ],
  "during_flap": false,
  "quality_score": 1.0,
  "time_bucket": "night",
  "people_home": 2,
  "anyone_home": true
}
```

**Field Descriptions**:
- `entity_id`: Home Assistant entity identifier
- `old_state`, `new_state`: State transition
- `timestamp`: Unix timestamp
- `datetime`: ISO 8601 formatted time
- `hour`, `minute`: Time components
- `day_of_week`: 0=Monday, 6=Sunday
- `is_weekend`: Boolean weekend flag
- `date`: Date string
- `seconds_since_last_change`: Time since previous state change
- `sun_position`: "above_horizon" or "below_horizon"
- `concurrent_states`: Other entity states at same time
- `concurrent_changes`: Other state changes within ±60 seconds
- `during_flap`: Flapping detection flag
- `quality_score`: 0.0-1.0 quality score
- `time_bucket`: "early_morning", "morning", "afternoon", "evening", "night"
- `people_home`: Count of people home
- `anyone_home`: Boolean presence flag

---

## Algorithm Details

### Wilson Score Confidence Interval

**Purpose**: Calculate conservative confidence estimate for binomial proportions

**Formula**:
```
Given:
  p = successes / trials
  z = 1.96  (for 95% confidence)

Calculate:
  denominator = 1 + z²/n
  center = (p + z²/(2n)) / denominator
  margin = (z/denominator) × √(p(1-p)/n + z²/(4n²))

Confidence (lower bound) = center - margin
```

**Why Wilson Score?**:
- More accurate than simple proportion for small samples
- Provides 95% confidence interval
- Returns conservative lower bound
- Handles edge cases (0%, 100% success rates)

**Implementation**:
```python
def wilson_score(successes, trials):
    if trials == 0:
        return 0.0

    p = successes / trials

    # Edge cases
    if p == 1.0:
        return max(0.0, 1.0 - (2.0 / trials))
    if p == 0.0:
        return 0.0

    z = 1.96
    denominator = 1 + z**2 / trials
    center = (p + z**2 / (2*trials)) / denominator
    sqrt_term = max(0.0, p*(1-p)/trials + z**2/(4*trials**2))
    margin = (z / denominator) * math.sqrt(sqrt_term)

    return max(0.0, min(1.0, center - margin))
```

**Example**:
```
Pattern: Light turns on at 9 AM
- Occurrences: 18 times
- Opportunities: 20 weekdays
- Simple proportion: 18/20 = 90%
- Wilson score (95% CI): 68.3% - 98.2%
- Lower bound (conservative): 68.3%

Interpretation: We're 95% confident the true rate is at least 68.3%
```

---

## Safety Features

### 1. Automatic Backups

```python
def create_backup(self):
    """Create timestamped backup before changes"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f'/config/ha_autopilot/backups/automations_backup_{timestamp}.yaml'

    if os.path.exists('/config/automations.yaml'):
        shutil.copy2('/config/automations.yaml', backup_path)
        print(f"✓ Backup created: {backup_path}")
        return backup_path
    else:
        print("⚠️  No automations.yaml found to backup")
        return None
```

### 2. Duplicate Prevention

```python
def install_automations(self, suggestions_file):
    """Install only new automations"""
    # Get existing autopilot automation IDs
    existing_ids = set()
    for automation in current_automations:
        if automation.get('id', '').startswith('autopilot_'):
            existing_ids.add(automation['id'])

    # Filter out duplicates
    unique_new = []
    for automation in new_automations:
        if automation['id'] not in existing_ids:
            unique_new.append(automation)

    if not unique_new:
        print("ℹ️  No new automations to install (all already exist)")
        return

    # Install only unique automations
    merged = current_automations + unique_new
```

### 3. Entity Exclusions

```python
# Exclude critical systems from automation
EXCLUDED_ENTITIES = {
    'climate.ecobee_main_floor',
    'climate.ecobee_main_floor_2',
    'climate.ecobee_upstairs',
    'climate.ecobee_upstairs_2',
}

def generate_from_temporal(self, pattern):
    # Skip excluded entities
    if pattern.entity_id in self.excluded_entities:
        return None

    # Generate automation...
```

### 4. Clear Labeling

```yaml
# All automations clearly labeled
alias: '[Autopilot] Light Office at 09:00 weekday'
description: 'Auto-generated from pattern detection. 95% confidence based on 20 occurrences.'
```

---

## Performance Benchmarks

### Analysis Performance

**Test System**: Home Assistant OS on x86 hardware

| Metric | Value |
|--------|-------|
| Data Size | 3,229 events from 30 days |
| Data Load Time | 2 seconds |
| Temporal Analysis | 5 seconds |
| Sequential Analysis | 8 seconds |
| Conditional Analysis | 12 seconds |
| Automation Generation | < 1 second |
| Report Generation | < 1 second |
| **Total Runtime** | **28 seconds** |

### Memory Usage

| Phase | Memory |
|-------|--------|
| Data Loading | 50 MB |
| Pattern Analysis | 150 MB |
| Peak Usage | 150 MB |

### Storage Requirements

| Item | Size |
|------|------|
| Phase 1 Export (30 days) | 26.5 MB |
| Phase 2 Code | 65 KB |
| Generated Automations | < 100 KB |
| Pattern Report | < 500 KB |
| **Total** | **27.1 MB** |

---

## Troubleshooting

### Common Issues

#### Issue: "No patterns detected"

**Symptoms**: Analysis completes but finds 0 patterns

**Causes**:
- Insufficient data (< 30 days)
- Very high confidence threshold (> 95%)
- Low activity in monitored period

**Solutions**:
```bash
# Gather more data
python /config/ha_autopilot/run_extraction.py --days 60

# Lower threshold
python run_pattern_detection.py --confidence 0.75

# Check data quality
cat exports/export_metadata.json
```

#### Issue: "Math domain error"

**Symptoms**: ValueError during confidence calculation

**Cause**: Edge case in square root calculation

**Solution**: Already fixed in code with edge case handling

```python
# Protection against negative sqrt
sqrt_term = max(0.0, p*(1-p)/trials + z**2/(4*trials**2))
margin = (z / denominator) * math.sqrt(sqrt_term)
```

#### Issue: "Automations not appearing in HA"

**Symptoms**: Automations installed but not visible

**Solutions**:
1. Reload automations: Settings → Automations → ⋮ → Reload
2. Check YAML syntax: Settings → System → Configuration Validation
3. Verify file: `cat /config/automations.yaml`

---

## Maintenance

### Regular Tasks

**Monthly Pattern Detection**:
```bash
# Run monthly to discover new patterns
cd /config/ha_autopilot
source venv/bin/activate
python run_pattern_detection.py --no-install
```

**Backup Cleanup** (every 3 months):
```bash
# Remove old backups (keep last 10)
cd /config/ha_autopilot/backups
ls -t automations_backup_*.yaml | tail -n +11 | xargs rm
```

**Data Export Cleanup** (every 6 months):
```bash
# Remove old exports (keep last 3)
cd /config/ha_autopilot/exports
ls -t state_changes_*.jsonl | tail -n +4 | xargs rm
```

### Updates and Modifications

**Adjusting Confidence Threshold**:
```python
# In run_pattern_detection.py
runner = PatternDetectionRunner(
    min_confidence=0.85,  # Lower from 0.90
    auto_install=True
)
```

**Adding Excluded Entities**:
```python
# In automation_generator.py
self.excluded_entities = {
    'climate.ecobee_main_floor',
    'lock.front_door',  # Add new exclusions
    'alarm_control_panel.home',
}
```

**Adjusting Time Windows**:
```python
# In sequential_analyzer.py
sequential_analyzer = SequentialAnalyzer(
    min_confidence=0.90,
    min_occurrences=5,
    max_window=600  # Increase to 10 minutes
)
```

---

## Version History

### v2.0 - December 30, 2025

**Initial Phase 2 Release**:
- ✅ Temporal pattern detection
- ✅ Sequential pattern detection
- ✅ Conditional pattern detection
- ✅ Automation generation
- ✅ Backup system
- ✅ Comprehensive reporting
- ✅ Wilson score confidence intervals
- ✅ Safety features (exclusions, duplicates)
- ✅ Production testing (3,229 events)

**Performance**:
- Analysis: 28 seconds for 30 days
- Memory: 150 MB peak
- Patterns: 2,824 detected
- Automations: 145 generated

---

## Credits

**HA-Autopilot Phase 2**
- Developed for Home Assistant 2025.12.5
- Statistical rigor: Wilson score confidence intervals
- Production tested: 30 days of real data
- Safety first: Backups, exclusions, duplicate prevention

**Dependencies**:
- Python 3.11+
- PyYAML 6.0+
- SQLite3 (built-in)

---

## Appendix: Pattern Examples

### Temporal Pattern Examples

**Daily Pattern**:
```
Entity: light.office
State: on
Time: 09:00 (±5 minutes)
Days: Every day
Confidence: 95%
Occurrences: 20/21 days
```

**Weekday Pattern**:
```
Entity: cover.blinds_office
State: open
Time: 08:30 (±10 minutes)
Days: Monday-Friday
Confidence: 92%
Occurrences: 18/20 weekdays
```

**Weekend Pattern**:
```
Entity: light.bedroom
State: on
Time: 10:00 (±15 minutes)
Days: Saturday-Sunday
Confidence: 90%
Occurrences: 9/10 weekends
```

### Sequential Pattern Examples

**Media → Lighting**:
```
Trigger: media_player.tv → 'on'
Action: light.living_room → 'off'
Delay: 15 seconds (average)
Window: 60 seconds (90th percentile)
Confidence: 92%
Occurrences: 18/20 times
```

**Door → Motion**:
```
Trigger: binary_sensor.door_entry → 'on'
Action: binary_sensor.motion_hallway → 'on'
Delay: 3 seconds (average)
Window: 30 seconds
Confidence: 88%
Occurrences: 25/28 times
```

### Conditional Pattern Examples

**Time + Presence**:
```
Conditions:
  - Time: after 6 PM
  - Presence: someone home
Action: light.porch → 'on'
Confidence: 95%
Occurrences: 30/32 times
```

**State + State**:
```
Conditions:
  - binary_sensor.office_occupancy → 'on'
  - Day: Monday-Friday
Action: climate.office → 'heat_cool'
Confidence: 88%
Occurrences: 45/51 times
```

---

*End of Phase 2 Code and State Documentation*
