-- Main pattern registry
CREATE TABLE ha_autopilot_patterns (
pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
pattern_type TEXT NOT NULL, -- ‘association’, ‘sequence’, ‘temporal’
pattern_hash TEXT UNIQUE, -- Dedupe check (hash of rule structure)

  -- Rule structure (stored as JSON for flexibility)
trigger_conditions TEXT NOT NULL, -- JSON: [{entity_id, state, context}]
action_target TEXT NOT NULL, -- JSON: {entity_id, service, params}

  -- Statistical metrics
confidence REAL NOT NULL, -- 0.0 to 1.0
support REAL NOT NULL, -- 0.0 to 1.0 (% of transactions)
lift REAL, -- Correlation strength vs random
conviction REAL, -- Implication strength
pattern_score REAL NOT NULL, -- Composite score

-- Temporal metadata
first_seen REAL NOT NULL, -- Unix timestamp
last_seen REAL NOT NULL, -- Unix timestamp
occurrence_count INTEGER NOT NULL, -- How many times observed

-- User interaction
user_feedback TEXT, -- NULL, ‘approved’, ‘rejected’, ‘ignored’
automation_id TEXT, -- HA automation ID if implemented
suggestion_shown BOOLEAN DEFAULT 0, -- Has user seen this suggestion?

-- Pattern lifecycle
status TEXT DEFAULT ‘active’, -- ‘active’, ‘deprecated’, ‘conflicting’
deprecated_by INTEGER, -- pattern_id that superseded this one
created_at REAL NOT NULL,
updated_at REAL NOT NULL,
FOREIGN KEY (deprecated_by) REFERENCES ha_autopilot_patterns(pattern_id)
);

-- Transaction records for pattern mining
CREATE TABLE ha_autopilot_transactions (
transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
window_start REAL NOT NULL, -- Unix timestamp
window_end REAL NOT NULL,
context_day_type TEXT, -- ‘weekday’, ‘weekend’
context_time_bucket TEXT, -- ‘morning’, ‘evening’, etc.
items TEXT NOT NULL, -- JSON: [{entity_id, state}]
quality_score REAL, -- Avg quality of events in transaction
created_at REAL NOT NULL
);

-- Sequential patterns need step tracking
CREATE TABLE ha_autopilot_sequences (
sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
pattern_id INTEGER NOT NULL,
step_order INTEGER NOT NULL, -- 1, 2, 3...
entity_id TEXT NOT NULL,
state TEXT NOT NULL,
typical_delay_seconds INTEGER, -- Time from previous step
FOREIGN KEY (pattern_id) REFERENCES ha_autopilot_patterns(pattern_id)
);

-- Pattern metadata and statistics
CREATE TABLE ha_autopilot_metadata (
key TEXT PRIMARY KEY,
value TEXT,
updated_at REAL NOT NULL
);

-- Indexes for performance
CREATE INDEX idx_patterns_type ON ha_autopilot_patterns(pattern_type);
CREATE INDEX idx_patterns_score ON ha_autopilot_patterns(pattern_score DESC);
CREATE INDEX idx_patterns_feedback ON ha_autopilot_patterns(user_feedback);
CREATE INDEX idx_patterns_status ON ha_autopilot_patterns(status);
CREATE INDEX idx_transactions_window ON ha_autopilot_transactions(window_start, window_end);
CREATE INDEX idx_sequences_pattern ON ha_autopilot_sequences(pattern_id);
