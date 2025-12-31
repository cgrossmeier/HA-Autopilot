#!/usr/bin/env python3
"""
Explore patterns in the extracted data.
"""

import sys
sys.path.insert(0, '/config/ha_autopilot')

from exporter import DataExporter
from collections import Counter
import glob
import os

# Find the most recent export file
export_dir = "/config/ha_autopilot/exports"
files = glob.glob(os.path.join(export_dir, "state_changes_*.jsonl"))
if not files:
    print("No export files found!")
    sys.exit(1)

latest_file = max(files, key=os.path.getctime)

exporter = DataExporter()
events = exporter.load_jsonl(latest_file)

print(f"\n{'='*70}")
print(f"Data Exploration Report")
print(f"File: {os.path.basename(latest_file)}")
print(f"{'='*70}\n")

# Most active entities
entity_counts = Counter(e["entity_id"] for e in events)
print("Most Active Entities (Top 15):")
print(f"{'Entity':<50} {'Events':>10}")
print("-" * 70)
for entity, count in entity_counts.most_common(15):
    print(f"{entity:<50} {count:>10}")

# Events by hour
hour_counts = Counter(e["hour"] for e in events)
print(f"\n{'='*70}")
print("Activity by Hour of Day:")
print(f"{'Hour':<10} {'Events':>10} {'Graph'}")
print("-" * 70)
max_count = max(hour_counts.values())
for hour in range(24):
    count = hour_counts.get(hour, 0)
    bar_length = int(40 * count / max_count) if max_count > 0 else 0
    bar = "█" * bar_length
    print(f"{hour:02d}:00     {count:>10} {bar}")

# Events by day of week
dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
dow_counts = Counter(e["day_of_week"] for e in events)
print(f"\n{'='*70}")
print("Activity by Day of Week:")
print(f"{'Day':<15} {'Events':>10} {'Graph'}")
print("-" * 70)
max_count = max(dow_counts.values())
for dow in range(7):
    count = dow_counts.get(dow, 0)
    bar_length = int(40 * count / max_count) if max_count > 0 else 0
    bar = "█" * bar_length
    print(f"{dow_names[dow]:<15} {count:>10} {bar}")

# Time buckets
time_bucket_counts = Counter(e.get("time_bucket", "unknown") for e in events)
print(f"\n{'='*70}")
print("Activity by Time of Day:")
print(f"{'Period':<20} {'Events':>10} {'Graph'}")
print("-" * 70)
bucket_order = ["early_morning", "morning", "midday", "afternoon", "evening", "night", "late_night"]
max_count = max(time_bucket_counts.values())
for bucket in bucket_order:
    count = time_bucket_counts.get(bucket, 0)
    bar_length = int(40 * count / max_count) if max_count > 0 else 0
    bar = "█" * bar_length
    print(f"{bucket:<20} {count:>10} {bar}")

# Quality scores
quality_counts = Counter()
for event in events:
    score = event.get("quality_score", 1.0)
    if score >= 0.9:
        quality_counts["High (>= 0.9)"] += 1
    elif score >= 0.7:
        quality_counts["Medium (0.7-0.9)"] += 1
    else:
        quality_counts["Low (< 0.7)"] += 1

print(f"\n{'='*70}")
print("Event Quality Distribution:")
print(f"{'Quality':<20} {'Events':>10} {'Percentage'}")
print("-" * 70)
total = len(events)
for quality, count in sorted(quality_counts.items(), reverse=True):
    pct = 100 * count / total if total > 0 else 0
    print(f"{quality:<20} {count:>10} {pct:>10.1f}%")

# Find patterns: What happens concurrently with specific events
print(f"\n{'='*70}")
print("Pattern Example: Concurrent State Analysis")
print("(Showing what other devices are typically in specific states)")
print("="*70)

# Example: What's usually on when lights turn on
light_events = [e for e in events if 'light' in e['entity_id'] and e['new_state'] == 'on']
if light_events:
    print(f"\nWhen lights turn on ({len(light_events)} times):")
    concurrent = Counter()
    for event in light_events[:100]:  # Sample first 100
        for entity, state in event.get("concurrent_states", {}).items():
            if state in ['on', 'home', 'playing', 'open']:  # Interesting states
                concurrent[(entity, state)] += 1

    print(f"{'Entity':<50} {'State':<15} {'Frequency'}")
    print("-" * 70)
    for (entity, state), count in concurrent.most_common(10):
        pct = 100 * count / min(len(light_events), 100)
        print(f"{entity:<50} {state:<15} {pct:>5.0f}%")

print(f"\n{'='*70}\n")
