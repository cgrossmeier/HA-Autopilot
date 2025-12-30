"""Constants for HA Autopilot pattern recognition."""

DOMAIN = "ha_autopilot"

# Pattern mining configuration
DEFAULT_MIN_SUPPORT = 0.10
DEFAULT_MIN_CONFIDENCE = 0.75
DEFAULT_MIN_LIFT = 1.2
DEFAULT_MIN_CONVICTION = 1.5

# Time windows for transaction building (seconds)
TRANSACTION_WINDOWS = {
    "short": 300,    # 5 minutes
    "medium": 900,   # 15 minutes
    "long": 1800,    # 30 minutes
}

# Quality thresholds
MIN_PATTERN_SCORE = 0.50
AUTO_SUGGEST_SCORE = 0.70
EXCELLENT_SCORE = 0.85

# Mining schedule
MINING_TIME = "03:00:00"
INCREMENTAL_MINING_INTERVAL = 7200

# Export paths
EXPORT_DIR = "/config/ha_autopilot/exports"
PATTERN_EXPORT_FILE = "patterns_for_review.json"

# Database table names
TABLE_PATTERNS = "ha_autopilot_patterns"
TABLE_TRANSACTIONS = "ha_autopilot_transactions"
TABLE_SEQUENCES = "ha_autopilot_sequences"
TABLE_METADATA = "ha_autopilot_metadata"

# Pattern types
PATTERN_TYPE_ASSOCIATION = "association"
PATTERN_TYPE_SEQUENCE = "sequence"
PATTERN_TYPE_TEMPORAL = "temporal"

# User feedback states
FEEDBACK_APPROVED = "approved"
FEEDBACK_REJECTED = "rejected"
FEEDBACK_IGNORED = "ignored"

# Pattern status
STATUS_ACTIVE = "active"
STATUS_DEPRECATED = "deprecated"
STATUS_CONFLICTING = "conflicting"
