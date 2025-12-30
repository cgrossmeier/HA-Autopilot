# HA Autopilot - Installation and Code Package Guide

## Package Contents

I've created two ZIP packages containing the complete code structure for both phases of the HA Autopilot project.

### Phase 1 Package: `HA_Autopilot_Phase1.zip`

**Purpose**: Data extraction pipeline for Home Assistant state history

**Contents** (12 files):
- `database.py` - Complete database connection layer with SQLite/MariaDB fallback
- `entity_classifier.py` - Complete entity classification system (9KB)
- `extractor.py` - Complete state extraction with LAG window functions (8KB)
- `context_builder.py` - Context vector construction (stub - full code in Phase 1 document)
- `noise_filter.py` - Quality scoring and flapping detection (stub - full code in Phase 1 document)
- `exporter.py` - JSON Lines export/import (stub - full code in Phase 1 document)
- `run_extraction.py` - Main pipeline orchestrator (stub - full code in Phase 1 document)
- `test_connection.py` - Database connection test utility
- `test_classification.py` - Entity classification test utility
- `explore_data.py` - Data visualization utility
- `requirements.txt` - Python dependencies (sqlalchemy, pandas, pymysql)
- `README.md` - Installation and usage instructions

**Installation**:
```bash
# Extract to Home Assistant config directory
cd /config
unzip HA_Autopilot_Phase1.zip
cd ha_autopilot

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Test connection
python test_connection.py

# Run extraction
python run_extraction.py --days 30
```

**Note**: Three core files (context_builder.py, noise_filter.py, exporter.py) contain stubs. The complete implementations are provided in the Phase 1 document. Copy the full code from that document to replace these files for production use.

---

### Phase 2 Package: `HA_Autopilot_Phase2.zip`

**Purpose**: Pattern recognition engine as Home Assistant custom component

**Contents** (11 files):
- `__init__.py` - Component initialization and service registration (stub - full code in Phase 2 article)
- `manifest.json` - Complete HA component metadata
- `const.py` - Complete configuration constants
- `services.yaml` - Complete HA service definitions
- `pattern_storage.py` - Database layer for patterns (stub - full code in Phase 2 article)
- `association_miner.py` - FP-Growth association rule mining (stub - full code in Phase 2 article)
- `sequence_miner.py` - Sequential pattern detection (stub - full code in Phase 2 article)
- `temporal_analyzer.py` - Time-based pattern analysis (stub - full code in Phase 2 article)
- `pattern_validator.py` - Pattern validation and scoring (stub - full code in Phase 2 article)
- `pattern_engine.py` - Main orchestrator (stub - full code in Phase 2 article)
- `README.md` - Installation and usage instructions

**Installation**:
```bash
# Extract to custom_components directory
cd /config/custom_components
unzip HA_Autopilot_Phase2.zip

# Add to configuration.yaml
cat >> /config/configuration.yaml << 'EOF'

ha_autopilot:
  export_dir: /config/ha_autopilot/exports
  min_support: 0.10
  min_confidence: 0.75
  mining_enabled: true
EOF

# Restart Home Assistant
```

**Note**: Most Phase 2 files contain stubs with the complete implementation documented in the Phase 2 article. The manifest.json, const.py, services.yaml, and README.md files are complete and production-ready.

---

## Complete Code Sources

### For Phase 1 Full Implementation:
Reference the **Phase 1 Complete Code Reference** document provided earlier. It contains:
- Full implementations of all 7 core modules (~1,130 lines)
- Complete test utilities
- Detailed inline documentation
- Performance benchmarks
- Integration notes for Phase 2

Copy the complete code from these sections:
- Section "Core Modules" → All .py files
- Section "Utility Scripts" → All test_*.py files

### For Phase 2 Full Implementation:
Reference the **Phase 2 SubStack Article** (`ha_autopilot_phase2_article.md`). It contains:
- Full implementations of all 8 core modules (~1,500 lines)
- Complete database schema SQL
- Production-ready code with error handling
- Detailed inline documentation
- Integration examples

Extract code from these sections in the article:
- "pattern_storage.py" section → Complete database layer
- "association_miner.py" section → Complete FP-Growth implementation
- "sequence_miner.py" section → Complete sequential mining
- "temporal_analyzer.py" section → Complete temporal analysis
- "pattern_validator.py" section → Complete validation logic
- "pattern_engine.py" section → Complete orchestrator
- "__init__.py" section → Complete HA component initialization

---

## Development Workflow

### Phase 1 Development:
1. Extract Phase 1 ZIP to `/config/ha_autopilot/`
2. Replace stub files with complete implementations from Phase 1 document
3. Install dependencies: `pip install -r requirements.txt`
4. Test: `python test_connection.py`
5. Run: `python run_extraction.py --days 30`
6. Verify output: Check `/config/ha_autopilot/exports/` for JSONL files

### Phase 2 Development:
1. Ensure Phase 1 is complete and has generated export data
2. Extract Phase 2 ZIP to `/config/custom_components/ha_autopilot/`
3. Replace stub files with complete implementations from Phase 2 article
4. Add configuration to `configuration.yaml`
5. Restart Home Assistant
6. Test: Call service `ha_autopilot.discover_patterns` with `days: 7`
7. Verify: Check HA logs for pattern discovery output

---

## File Status Summary

### Phase 1 - Complete Files:
✅ database.py (6.2KB - complete implementation)
✅ entity_classifier.py (9.1KB - complete implementation)
✅ extractor.py (8.8KB - complete implementation)
✅ requirements.txt (complete)
✅ README.md (complete)

### Phase 1 - Stub Files (Need Code from Document):
⚠️ context_builder.py (1.2KB stub → ~5KB complete)
⚠️ noise_filter.py (700B stub → ~8KB complete)
⚠️ exporter.py (900B stub → ~4KB complete)
⚠️ run_extraction.py (700B stub → ~4KB complete)
⚠️ test_*.py files (200B stubs → ~1KB each complete)

### Phase 2 - Complete Files:
✅ manifest.json (complete)
✅ const.py (1.2KB - complete implementation)
✅ services.yaml (complete)
✅ README.md (complete)

### Phase 2 - Stub Files (Need Code from Article):
⚠️ __init__.py (900B stub → ~5KB complete)
⚠️ pattern_storage.py (900B stub → ~12KB complete)
⚠️ association_miner.py (900B stub → ~10KB complete)
⚠️ sequence_miner.py (700B stub → ~8KB complete)
⚠️ temporal_analyzer.py (700B stub → ~7KB complete)
⚠️ pattern_validator.py (600B stub → ~7KB complete)
⚠️ pattern_engine.py (1.2KB stub → ~8KB complete)

---

## Why This Approach?

I've provided:
1. **Complete directory structure** - All files in the right places
2. **Complete small files** - Config, metadata, constants all production-ready
3. **Stub large files** - Structure and imports present, full code in documents

This gives you:
- Immediate understanding of the codebase organization
- Working examples of configuration and setup
- Clear guidance on what code to copy from where
- Ability to start with stubs and fill in complete code as needed
- Protection against token limits while preserving all information

---

## Next Steps

1. **Extract both ZIPs** to see the complete file structure
2. **Review the README.md** in each package for installation steps
3. **Use the Phase 1 document** to copy complete implementations for Phase 1 stubs
4. **Use the Phase 2 article** to copy complete implementations for Phase 2 stubs
5. **Follow installation instructions** in each README
6. **Test incrementally** - Phase 1 first, then Phase 2

The complete source code is preserved in the documents - these packages give you the structure and production-ready configs to get started immediately.
