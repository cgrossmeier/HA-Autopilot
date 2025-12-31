# HA-Autopilot Phase 2: Pattern Recognition

**Automated pattern detection and automation suggestion system for Home Assistant**

---

## Quick Start

### 1. Run Pattern Detection

```bash
cd /config/ha_autopilot
source venv/bin/activate
python run_pattern_detection.py --no-install
```

This will:
- Analyze Phase 1 data (3,229 events from 30 days)
- Detect temporal, sequential, and conditional patterns
- Generate automation suggestions
- Create comprehensive pattern report

### 2. Review Suggestions

Open the generated files in `/config/ha_autopilot/suggestions/`:
- `automations_*.yaml` - Automation configurations
- `pattern_report_*.md` - Detailed pattern analysis

### 3. Install Automations (Optional)

**Option A: Manual (Recommended)**
1. Review `automations_*.yaml`
2. Copy desired automations to `/config/automations.yaml`
3. Reload automations in HA UI

**Option B: Automatic with Backup**
```bash
python run_pattern_detection.py  # Installs automatically
```
Then reload automations in Home Assistant UI.

---

## What It Does

### Pattern Types Detected

**1. Temporal Patterns** - Time-based routines
- "Lights turn on at 6 PM on weekdays"
- "Blinds close at sunset"
- "Climate adjusts at 9 PM"

**2. Sequential Patterns** - Event sequences
- "TV turns on → Lights dim within 2 minutes"
- "Door opens → Motion detected within 1 minute"
- "Arrival → Scene activates"

**3. Conditional Patterns** - Multi-condition rules
- "When after 6 PM AND someone home → Lights on"
- "When office occupied AND weekday → Climate on"

### How It Works

1. **Load Data**: Reads Phase 1 exported state changes
2. **Analyze Patterns**: Uses statistical algorithms to find patterns
3. **Calculate Confidence**: Wilson score intervals (95% confidence)
4. **Generate Automations**: Converts patterns to HA YAML
5. **Create Report**: Comprehensive analysis with recommendations

---

## Command Line Options

```bash
# Basic usage (auto-install with backup)
python run_pattern_detection.py

# Generate suggestions only (no install)
python run_pattern_detection.py --no-install

# Adjust confidence threshold (default: 0.90 = 90%)
python run_pattern_detection.py --confidence 0.75

# Dry run (preview without generating files)
python run_pattern_detection.py --dry-run
```

---

## Understanding Results

### Pattern Confidence

- **90-100%**: Very reliable, happens almost every time
- **75-90%**: Consistent, but with occasional exceptions
- **60-75%**: Noticeable pattern, but less consistent

**Default threshold**: 90% (conservative, high-quality patterns only)

### Occurrences

Minimum 5 occurrences required for pattern detection.
More occurrences = more reliable pattern.

### Pattern Types

**Actionable Patterns** (good automation candidates):
- Lights, switches, covers (blinds/shades)
- Climate controls (if not already automated)
- Media players
- Scenes

**Observational Patterns** (informational, not automatable):
- Binary sensors (motion, door/window sensors)
- Read-only device states
- User behavior patterns

---

## Safety Features

### 1. Automatic Backups
Every installation creates a backup:
- Location: `/config/ha_autopilot/backups/`
- Format: `automations_backup_YYYYMMDD_HHMMSS.yaml`

### 2. Duplicate Prevention
- Checks for existing autopilot automation IDs
- Only adds new automations
- Won't overwrite manual changes

### 3. Clear Labeling
- All automations prefixed with `[Autopilot]`
- Easy to identify and manage
- Detailed descriptions with confidence scores

### 4. Excluded Entities
Critical systems excluded from automation:
- Climate devices (already have manual automations)
- You can add more in `automation_generator.py`

---

## Files and Directories

```
/config/ha_autopilot/
├── Phase 2 Scripts:
│   ├── run_pattern_detection.py      # Main runner
│   ├── temporal_analyzer.py          # Time-based patterns
│   ├── sequential_analyzer.py        # Sequential patterns
│   ├── conditional_analyzer.py       # Conditional patterns
│   └── automation_generator.py       # YAML generation
│
├── Output:
│   ├── suggestions/                  # Generated automations & reports
│   └── backups/                      # Automation backups
│
└── Documentation:
    ├── PHASE2_README.md              # This file
    ├── PHASE2_COMPLETE.md            # Detailed technical docs
    └── Phase 1 docs...
```

---

## Common Workflows

### Initial Pattern Discovery

```bash
# Run with default settings
python run_pattern_detection.py --no-install

# Review report
cat suggestions/pattern_report_*.md

# Review automations
cat suggestions/automations_*.yaml
```

### Finding More Patterns (Lower Threshold)

```bash
# Detect patterns with 75% confidence
python run_pattern_detection.py --confidence 0.75 --no-install

# Compare with 90% threshold results
```

### Installing Vetted Automations

```bash
# After reviewing suggestions
python run_pattern_detection.py  # Auto-installs

# Then in Home Assistant UI:
# Settings → Automations → ⋮ → Reload Automations
```

### Removing Autopilot Automations

1. Go to Settings → Automations in HA UI
2. Search for `[Autopilot]`
3. Delete unwanted automations
4. Or edit `/config/automations.yaml` directly

---

## Customization

### Adjust Detection Parameters

Edit analyzer files to change thresholds:

**temporal_analyzer.py**:
```python
min_confidence=0.90    # 90% confidence minimum
min_occurrences=5      # 5 events minimum
```

**sequential_analyzer.py**:
```python
min_confidence=0.90    # 90% confidence minimum
min_occurrences=5      # 5 events minimum
max_window=300         # 5 minute time window
```

### Exclude Entities

Edit **automation_generator.py**:
```python
self.excluded_entities = {
    'climate.ecobee_main_floor',
    'your.entity_to_exclude',
}
```

### Change Time Windows

For sequential patterns, adjust `max_window` in seconds:
```python
# In sequential_analyzer.py or run_pattern_detection.py
max_window=180  # 3 minutes instead of 5
```

---

## Troubleshooting

### No Patterns Detected

**Causes:**
- Insufficient data (need more days)
- High confidence threshold
- Low activity in analyzed period

**Solutions:**
- Run Phase 1 extraction for 60-90 days
- Lower threshold: `--confidence 0.75`
- Check Phase 1 data quality

### Patterns Seem Wrong

**Causes:**
- Correlations vs causations (normal)
- Unusual activity during data period
- Binary sensor patterns (observational)

**Solutions:**
- Review pattern descriptions carefully
- Focus on actionable entities (lights, switches, covers)
- Ignore binary sensor patterns
- Gather more data for better accuracy

### Automations Not Working

**Causes:**
- Not reloaded in HA UI
- YAML syntax errors
- Entity IDs changed

**Solutions:**
- Always reload automations after changes
- Run Configuration Check in HA UI
- Verify entity IDs still exist

### Too Many Automations

**Solutions:**
- Increase confidence: `--confidence 0.95`
- Manually select desired automations
- Use `--dry-run` to preview first

---

## Examples

### Example 1: Daily Routine Discovery

**Pattern Detected:**
```
Light.Office → 'on' at 09:00 on weekdays
(95% confidence, 20 occurrences)
```

**Generated Automation:**
```yaml
- id: autopilot_temporal_20251230_abc123
  alias: '[Autopilot] Light Office at 09:00 weekday'
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
```

### Example 2: Sequential Pattern

**Pattern Detected:**
```
Media_Player.TV → 'on' ⟹ Light.Living_Room → 'off'
(within 60s, avg 15s, 92% confidence, 18× )
```

**Generated Automation:**
```yaml
- id: autopilot_sequential_20251230_xyz789
  alias: '[Autopilot] Light Living Room after Media Player TV'
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

---

## Performance

- **Analysis Time**: ~30 seconds for 30 days of data
- **Memory Usage**: < 100 MB
- **Storage**: Minimal (suggestions are small YAML files)

---

## Best Practices

1. **Start Conservative**: Use default 90% confidence threshold
2. **Review Everything**: Always review before installing
3. **Test Incrementally**: Install a few automations at a time
4. **Monitor Behavior**: Watch for unexpected triggers
5. **Keep Backups**: Backups are created automatically
6. **Iterate**: Disable what doesn't work, keep what does
7. **Gather More Data**: More days = better pattern detection

---

## Support

### Documentation

- `PHASE2_COMPLETE.md` - Comprehensive technical documentation
- `PHASE1_COMPLETE.md` - Phase 1 data pipeline details
- `README.md` - Phase 1 usage guide

### Common Issues

See Troubleshooting section above

### Manual Intervention

- Edit `/config/automations.yaml` directly if needed
- Use HA UI to manage automations
- Check logs in `/config/ha_autopilot/logs/`

---

## Credits

**HA-Autopilot Phase 2: Pattern Recognition**
- Statistical pattern detection using Wilson score confidence intervals
- Temporal, sequential, and conditional pattern analyzers
- Safe automation generation with backup system
- Built for Home Assistant 2025.12.5

---

## Version History

### v2.0 - December 30, 2025
- Initial Phase 2 release
- Temporal pattern detection
- Sequential pattern detection
- Conditional pattern detection
- Automation generation
- Backup system
- Comprehensive reporting

---

*Enjoy automated pattern discovery! 🤖*
