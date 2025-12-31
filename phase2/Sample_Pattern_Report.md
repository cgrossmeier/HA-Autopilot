# HA-Autopilot Phase 2: Pattern Detection Report
**Generated**: 2025-12-10 15:51:27

**Confidence Threshold**: 90%

---

## Summary

- **Total Patterns Detected**: 2824
  - Temporal (time-based): 140
  - Sequential (A→B): 5
  - Conditional (if-then): 2679
- **Automations Generated**: 145
- **Suggestions File**: `automations_20251210_155126.yaml`

## Temporal Patterns (140)

Time-based patterns that occur regularly:

1. Binary Sensor.Refrigerator Cooler Door → 'on' at 09:09-43 every day (100% confidence, 30 times)
2. Binary Sensor.Refrigerator Cooler Door → 'off' at 09:09-43 every day (100% confidence, 30 times)
3. Binary Sensor.Refrigerator Cooler Door → 'on' at 09:14-43 on weekends (100% confidence, 24 times)
4. Binary Sensor.Refrigerator Cooler Door → 'off' at 09:14-43 on weekends (100% confidence, 24 times)
5. Binary Sensor.Multipurpose Sensor 1 Acceleration → 'off' at 10:00-57 every day (100% confidence, 22 times)
6. Binary Sensor.Multipurpose Sensor 1 Acceleration → 'on' at 10:00-57 every day (100% confidence, 21 times)
7. Binary Sensor.Refrigerator Cooler Door → 'on' at 17:02-54 every day (100% confidence, 19 times)
8. Binary Sensor.Refrigerator Cooler Door → 'off' at 17:03-54 every day (100% confidence, 19 times)
9. Binary Sensor.Door Kitchen Contact → 'on' at 12:11-59 every day (100% confidence, 17 times)
10. Binary Sensor.Door Kitchen Contact → 'off' at 12:11-59 every day (100% confidence, 17 times)
11. Binary Sensor.Multipurpose Sensor 1 Acceleration → 'on' at 10:03-57 on weekdays (100% confidence, 16 times)
12. Binary Sensor.Multipurpose Sensor 1 Acceleration → 'on' at 15:04-54 every day (100% confidence, 16 times)
13. Binary Sensor.Multipurpose Sensor 1 Acceleration → 'off' at 10:03-57 on weekdays (100% confidence, 16 times)
14. Binary Sensor.Multipurpose Sensor 1 Acceleration → 'off' at 15:05-55 every day (100% confidence, 16 times)
15. Binary Sensor.Door Kitchen Contact → 'on' at 12:11-59 on weekends (100% confidence, 16 times)
16. Binary Sensor.Door Kitchen Contact → 'off' at 12:11-59 on weekends (100% confidence, 16 times)
17. Binary Sensor.Refrigerator Cooler Door → 'on' at 09:14-27 every Sun (100% confidence, 13 times)
18. Binary Sensor.Refrigerator Cooler Door → 'on' at 13:01-52 every day (100% confidence, 13 times)
19. Binary Sensor.Refrigerator Cooler Door → 'on' at 17:03-47 on weekdays (100% confidence, 13 times)
20. Binary Sensor.Refrigerator Cooler Door → 'off' at 09:14-27 every Sun (100% confidence, 13 times)

... and 120 more

## Sequential Patterns (5)

Event sequences where one action triggers another:

1. Media Player.Unnamed Room → 'paused' ⟹ Media Player.Living Room 4 → 'paused' (within 0s, avg 0s, 93% confidence, 32× )
2. Binary Sensor.All Doors → 'off' ⟹ Binary Sensor.All Doorsand Windows → 'off' (within 0s, avg 0s, 90% confidence, 22× )
3. Binary Sensor.All Doors → 'on' ⟹ Binary Sensor.All Doorsand Windows → 'on' (within 0s, avg 0s, 90% confidence, 21× )
4. Media Player.Television 3 → 'off' ⟹ Switch.Television → 'off' (within 0s, avg 0s, 90% confidence, 20× )
5. Media Player.Television 3 → 'on' ⟹ Switch.Television → 'on' (within 0s, avg 0s, 90% confidence, 20× )

## Conditional Patterns (2679)

Patterns that occur under specific conditions:

1. When someone is home ⟹ Binary Sensor.Refrigerator Cooler Door → 'on' (98% confidence, 119×)
2. When Binary Sensor.Someone Enters Office Occupancy is 'off' ⟹ Binary Sensor.Refrigerator Cooler Door → 'on' (98% confidence, 119×)
3. When Binary Sensor.Window Master Bedroom Door is 'unavailable' ⟹ Binary Sensor.Refrigerator Cooler Door → 'on' (98% confidence, 119×)
4. When Switch.Home Off Grid Operation is 'off' ⟹ Binary Sensor.Refrigerator Cooler Door → 'on' (98% confidence, 119×)
5. When someone is home ⟹ Binary Sensor.Refrigerator Cooler Door → 'off' (98% confidence, 119×)
6. When Binary Sensor.Someone Enters Office Occupancy is 'off' ⟹ Binary Sensor.Refrigerator Cooler Door → 'off' (98% confidence, 119×)
7. When Binary Sensor.Window Master Bedroom Door is 'unavailable' ⟹ Binary Sensor.Refrigerator Cooler Door → 'off' (98% confidence, 119×)
8. When Switch.Home Off Grid Operation is 'off' ⟹ Binary Sensor.Refrigerator Cooler Door → 'off' (98% confidence, 119×)
9. When someone is home ⟹ Binary Sensor.Multipurpose Sensor 1 Acceleration → 'on' (97% confidence, 85×)
10. When Binary Sensor.Absence From Office Occupancy is 'off' ⟹ Binary Sensor.Multipurpose Sensor 1 Acceleration → 'on' (97% confidence, 85×)
11. When Binary Sensor.Aqara Door And Window Sensor Door is 'off' ⟹ Binary Sensor.Multipurpose Sensor 1 Acceleration → 'on' (97% confidence, 85×)
12. When Binary Sensor.Aqara Fp2 16D9 Presence is 'on' ⟹ Binary Sensor.Multipurpose Sensor 1 Acceleration → 'on' (97% confidence, 85×)
13. When Binary Sensor.Refrigerator Cooler Door is 'off' ⟹ Binary Sensor.Multipurpose Sensor 1 Acceleration → 'on' (97% confidence, 85×)
14. When Binary Sensor.Someone Enters Office Occupancy is 'off' ⟹ Binary Sensor.Multipurpose Sensor 1 Acceleration → 'on' (97% confidence, 85×)
15. When Switch.Home Off Grid Operation is 'off' ⟹ Binary Sensor.Multipurpose Sensor 1 Acceleration → 'on' (97% confidence, 85×)
16. When someone is home ⟹ Binary Sensor.Multipurpose Sensor 1 Acceleration → 'off' (97% confidence, 85×)
17. When Binary Sensor.Absence From Office Occupancy is 'off' ⟹ Binary Sensor.Multipurpose Sensor 1 Acceleration → 'off' (97% confidence, 85×)
18. When Binary Sensor.Aqara Door And Window Sensor Door is 'off' ⟹ Binary Sensor.Multipurpose Sensor 1 Acceleration → 'off' (97% confidence, 85×)
19. When Binary Sensor.Refrigerator Cooler Door is 'off' ⟹ Binary Sensor.Multipurpose Sensor 1 Acceleration → 'off' (97% confidence, 85×)
20. When Binary Sensor.Someone Enters Office Occupancy is 'off' ⟹ Binary Sensor.Multipurpose Sensor 1 Acceleration → 'off' (97% confidence, 85×)

... and 2659 more

---

## Next Steps

1. **Review Automations**: Open `automations_20251210_155126.yaml` and review each automation
2. **Test in UI**: Go to Settings → Automations in Home Assistant
3. **Manual Install**: Copy desired automations to automations.yaml
4. **Reload**: Reload automations in Home Assistant UI

---

## Backup Information

No backup created (automations not installed automatically).
