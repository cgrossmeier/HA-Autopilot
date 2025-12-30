"""
Entity classification for HA-Autopilot.
Determines which entities produce meaningful state changes.

Classification Strategy:
- High Signal: Lights, switches, locks, doors, windows, motion, presence
- Medium Signal: Climate, vacuum, fans (less frequent but meaningful)
- Low Signal: Most sensors (continuous updates, low value)
- Exclude: Weather, sun, automations, device trackers

Phase 2 Usage:
Entity classifications can be used to weight patterns differently.
High-signal entities might receive higher confidence scores.
"""

from sqlalchemy import text
from typing import Set, Dict, List
import logging
import json

logger = logging.getLogger(__name__)


# Domain-level classification
# These domains always produce meaningful state changes
HIGH_SIGNAL_DOMAINS = {
    "light", "switch", "lock", "cover", "media_player",
    "input_boolean", "person", "input_select"
}

# Medium signal domains - meaningful but less frequent
MEDIUM_SIGNAL_DOMAINS = {
    "climate", "fan", "vacuum", "humidifier", "water_heater"
}

# Binary sensor device classes that indicate meaningful events
# These are high-value triggers for automations
HIGH_SIGNAL_BINARY_CLASSES = {
    "door", "window", "motion", "occupancy", "presence",
    "garage_door", "lock", "opening", "safety"
}

# Medium signal binary sensors
MEDIUM_SIGNAL_BINARY_CLASSES = {
    "plug", "running", "moving", "sound", "vibration"
}

# Always exclude these domains - they don't represent user actions
EXCLUDE_DOMAINS = {
    "weather", "sun", "automation", "script", "scene",
    "persistent_notification", "zone", "device_tracker",
    "update", "button", "number", "select", "text"
}


class EntityClassifier:
    """
    Classifies Home Assistant entities by signal quality.

    Methodology:
    1. Check custom includes/excludes first (user override)
    2. Check domain-level exclusions
    3. Check high/medium signal domains
    4. For binary_sensor, inspect device_class
    5. Default to low signal

    Args:
        db_connector: DatabaseConnector instance
        custom_includes: Set of entity_ids to always include
        custom_excludes: Set of entity_ids to always exclude

    Example:
        classifier = EntityClassifier(db)
        entities = classifier.get_filtered_entities(min_signal="high")
        # Returns only high-signal entities
    """

    def __init__(self, db_connector, custom_includes: Set[str] = None,
                 custom_excludes: Set[str] = None):
        self.db = db_connector
        self.custom_includes = custom_includes or set()
        self.custom_excludes = custom_excludes or set()

        # Caching for performance
        self._entity_cache = None
        self._attribute_cache = {}

    def get_all_entities(self) -> List[Dict]:
        """
        Fetch all entities from states_meta.

        Home Assistant Schema:
        - states_meta: Maps metadata_id to entity_id
        - Used for efficient entity lookups in states table

        Returns:
            List of dicts with metadata_id, entity_id, domain
        """
        if self._entity_cache is not None:
            return self._entity_cache

        with self.db.get_connection() as conn:
            # Get all entity IDs
            result = conn.execute(text("""
                SELECT metadata_id, entity_id
                FROM states_meta
                ORDER BY entity_id
            """))

            entities = []
            for row in result:
                entity_id = row[1]
                domain = entity_id.split(".")[0]

                entities.append({
                    "metadata_id": row[0],
                    "entity_id": entity_id,
                    "domain": domain
                })

            self._entity_cache = entities
            logger.info(f"Loaded {len(entities)} entities from database")
            return entities

    def get_entity_device_class(self, entity_id: str) -> str:
        """
        Look up the device_class attribute for an entity.

        Device class provides semantic meaning for binary sensors.
        Examples: "door", "window", "motion", "occupancy"

        Args:
            entity_id: Entity to query

        Returns:
            device_class string or None if not found

        Phase 2 Note:
            Device class can be used to create semantic categories
            for pattern grouping (e.g., all "door" sensors together).
        """
        if entity_id in self._attribute_cache:
            return self._attribute_cache[entity_id]

        with self.db.get_connection() as conn:
            # Find the most recent state with attributes
            result = conn.execute(text("""
                SELECT sa.shared_attrs
                FROM states s
                JOIN states_meta sm ON s.metadata_id = sm.metadata_id
                JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
                WHERE sm.entity_id = :entity_id
                AND sa.shared_attrs IS NOT NULL
                ORDER BY s.last_updated_ts DESC
                LIMIT 1
            """), {"entity_id": entity_id})

            row = result.fetchone()
            if row and row[0]:
                try:
                    attrs = json.loads(row[0])
                    device_class = attrs.get("device_class")
                    self._attribute_cache[entity_id] = device_class
                    return device_class
                except json.JSONDecodeError:
                    pass

            self._attribute_cache[entity_id] = None
            return None

    def classify_entity(self, entity_id: str, domain: str) -> str:
        """
        Classify a single entity.

        Classification Hierarchy:
        1. Custom overrides (highest priority)
        2. Domain-level exclusions
        3. High signal domains
        4. Medium signal domains
        5. Binary sensor device_class inspection
        6. Default to low signal

        Returns: 'high', 'medium', 'low', or 'exclude'
        """
        # Custom overrides take precedence
        if entity_id in self.custom_excludes:
            return "exclude"
        if entity_id in self.custom_includes:
            return "high"

        # Domain-level exclusions
        if domain in EXCLUDE_DOMAINS:
            return "exclude"

        # High signal domains
        if domain in HIGH_SIGNAL_DOMAINS:
            return "high"

        # Medium signal domains
        if domain in MEDIUM_SIGNAL_DOMAINS:
            return "medium"

        # Binary sensors need device_class inspection
        if domain == "binary_sensor":
            device_class = self.get_entity_device_class(entity_id)
            if device_class in HIGH_SIGNAL_BINARY_CLASSES:
                return "high"
            if device_class in MEDIUM_SIGNAL_BINARY_CLASSES:
                return "medium"
            return "low"

        # Sensors are generally low signal (too noisy)
        if domain == "sensor":
            return "low"

        # Default to low for unknown domains
        return "low"

    def get_filtered_entities(self,
                              include_medium: bool = True,
                              min_signal: str = "medium") -> List[Dict]:
        """
        Get list of entities that pass the signal filter.

        Args:
            include_medium: Include medium-signal entities
            min_signal: Minimum signal level ('high' or 'medium')

        Returns:
            List of entity dicts with classification added

        Phase 2 Usage:
            Pattern recognition can use different entity sets:
            - High-only for critical patterns
            - High+Medium for comprehensive patterns
        """
        all_entities = self.get_all_entities()
        filtered = []

        for entity in all_entities:
            classification = self.classify_entity(
                entity["entity_id"],
                entity["domain"]
            )

            if classification == "exclude":
                continue

            if classification == "low":
                continue

            if classification == "medium" and min_signal == "high":
                continue

            entity["signal_level"] = classification
            filtered.append(entity)

        logger.info(f"Filtered to {len(filtered)} entities from {len(all_entities)} total")
        return filtered

    def generate_report(self) -> Dict:
        """
        Generate a classification report for all entities.
        Useful for tuning the filter configuration.

        Returns:
            Dict with counts and entity lists by classification
        """
        all_entities = self.get_all_entities()

        report = {
            "high": [],
            "medium": [],
            "low": [],
            "exclude": []
        }

        for entity in all_entities:
            classification = self.classify_entity(
                entity["entity_id"],
                entity["domain"]
            )
            report[classification].append(entity["entity_id"])

        return {
            "counts": {k: len(v) for k, v in report.items()},
            "entities": report
        }
