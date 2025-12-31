# Initial Data Analysis - HA-Autopilot Phase 1

## Extraction Summary

**Date**: December 29, 2025
**Period Analyzed**: 7 days (Dec 22-29, 2025)
**Total Events**: 1,972 state changes
**Active Entities**: 65 out of 175 monitored
**Data Quality**: 83.3% high quality events

---

## Key Patterns Discovered

### Most Active Devices

1. **Refrigerator Door Sensor** - 143 events
   - Opens ~20 times per day
   - Primary kitchen activity indicator

2. **Kitchen Door Contact** - 110 events
   - High traffic area
   - ~15 opens per day

3. **Office Presence Sensors** (Aqara FP2) - 167 combined events
   - Clear work pattern
   - Office usage tracking

4. **Media Players** - 308 combined events
   - Living room TV most active (98 events)
   - Sonos speakers show usage patterns

### Activity Patterns

#### By Time of Day
- **Peak Activity**: 4:00 PM (198 events)
- **Morning Rush**: 9:00-10:00 AM (333 events)
- **Quietest**: 6:00 AM (8 events)

**Pattern**: Clear bimodal distribution
- Morning peak: 9 AM - 1 PM
- Afternoon/Evening peak: 3 PM - 11 PM

#### By Day of Week
- **Saturday**: Most active (581 events, 29% of total)
- **Sunday**: Second most active (416 events, 21%)
- **Tuesday**: Least active (112 events, 6%)

**Pattern**: 50% of all activity happens on weekends, suggesting home-focused activities.

#### By Period
1. **Morning** (9am-12pm): 457 events - Highest activity
2. **Afternoon** (2pm-5pm): 352 events
3. **Midday** (12pm-2pm): 292 events
4. **Late Night** (11pm-5am): 290 events - Surprisingly active
5. **Evening** (5pm-8pm): 226 events
6. **Night** (8pm-11pm): 224 events
7. **Early Morning** (5am-9am): 131 events

### Concurrent Patterns

When lights turn on, the following are almost always true:
- Multiple presence sensors active (100%)
- Phones/iPads connected (100%)
- Door sensors in specific states (100%)
- Automation switches enabled (100%)

**Insight**: Strong correlation between presence detection and lighting suggests existing automations are working, but there may be opportunities for refinement.

---

## Entity Health

### Signal Quality Distribution

- **High Quality** (≥0.9): 1,643 events (83.3%)
- **Medium Quality** (0.7-0.9): 71 events (3.6%)
- **Low Quality** (<0.7): 258 events (13.1%)

**Analysis**: 88 events were filtered out due to low activity. The remaining dataset is predominantly high quality.

### Monitored Entity Breakdown

**Active** (65 entities producing events):
- Binary Sensors: ~30 (doors, windows, motion, presence)
- Media Players: ~15 (Sonos, TV, Spotify)
- Lights: ~8 (various rooms)
- Covers: ~7 (motorized blinds)
- Climate: ~2 (Ecobee thermostats)
- Switches: ~3

**Inactive** (110 entities with no events in 7 days):
- Likely: Battery-powered devices in static states
- Possibly: Disabled integrations
- Maybe: Rarely used devices

---

## Automation Opportunities

Based on these patterns, potential automations to explore in Phase 2:

### 1. Kitchen Activity Based Lighting
- Refrigerator door opens correlate with kitchen presence
- Could auto-activate kitchen lights during evening hours

### 2. Office Presence Optimization
- Office sensors show clear work schedule
- Climate control could auto-adjust based on presence patterns

### 3. Weekend vs Weekday Modes
- Dramatically different activity profiles
- Separate automation sets for weekday/weekend

### 4. Late Night Activity
- Significant activity 11 PM - 5 AM (290 events)
- Night mode automations could be optimized

### 5. Media Player Triggers
- Living room media players show consistent patterns
- Could trigger scene adjustments automatically

---

## Data Pipeline Performance

### Extraction Metrics
- **Database Size**: 1,386,706 total state records
- **Total Entities**: 1,085 in system
- **Filtered To**: 175 high/medium signal entities
- **Extraction Time**: 6 seconds
- **Event Reduction**: 4.3% filtered (2,060 → 1,972)

### Storage
- **Output Size**: 15.8 MB for 7 days
- **Projected 30 days**: ~68 MB
- **Projected 90 days**: ~204 MB

---

## Recommendations

### 1. Run 30-Day Extraction
Get more comprehensive patterns:
```bash
cd /config/ha_autopilot
source venv/bin/activate
python run_extraction.py --days 30
```

### 2. Include Medium-Signal Entities
Capture climate and vacuum patterns:
```bash
python run_extraction.py --days 30 --include-medium
```

### 3. Schedule Daily Incremental Runs
Keep dataset current with daily 1-day extractions

### 4. Review Inactive Entities
110 entities had no events - verify these are expected to be inactive

### 5. Investigate Late Night Patterns
290 events between 11 PM - 5 AM warrant investigation:
- Automated processes?
- Security events?
- Legitimate usage?

---

## Next Phase

With this foundation data, Phase 2 can begin pattern recognition to:

1. **Identify correlations** between devices
2. **Find temporal patterns** (time-of-day, day-of-week)
3. **Detect sequences** (X happens, then Y happens within N minutes)
4. **Calculate confidence scores** for pattern reliability
5. **Generate automation suggestions** with explanations

The data shows your home has clear patterns ready to be automated!
