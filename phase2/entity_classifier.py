"""
Entity classification for HA-Autopilot.
Determines which entities produce meaningful state changes.
"""

from sqlalchemy import text
from typing import Set, Dict, List
import logging
import json

logger = logging.getLogger(__name__)


# Domain-level classification
HIGH_SIGNAL_DOMAINS = {
    "light", "switch", "lock", "cover", "media_player",
    "input_boolean", "person", "input_select"
}

MEDIUM_SIGNAL_DOMAINS = {
    "climate", "fan", "vacuum", "humidifier", "water_heater"
}

# Binary sensor device classes that indicate meaningful events
HIGH_SIGNAL_BINARY_CLASSES = {
    "door", "window", "motion", "occupancy", "presence",
    "garage_door", "lock", "opening", "safety"
}

MEDIUM_SIGNAL_BINARY_CLASSES = {
    "plug", "running", "moving", "sound", "vibration"
}

# Always exclude these domains
EXCLUDE_DOMAINS = {
    "weather", "sun", "automation", "script", "scene",
    "persistent_notification", "zone", "device_tracker",
    "update", "button", "number", "select", "text"
}


class EntityClassifier:
    """
    Classifies Home Assistant entities by signal quality.

    Args:
        db_connector: DatabaseConnector instance
        custom_includes: Set of entity_ids to always include
        custom_excludes: Set of entity_ids to always exclude
    """

    def __init__(self, db_connector, custom_includes: Set[str] = None,
                 custom_excludes: Set[str] = None):
        self.db = db_connector
        self.custom_includes = custom_includes or set()
        self.custom_excludes = custom_excludes or set()

        self._entity_cache = None
        self._attribute_cache = {}

    def get_all_entities(self) -> List[Dict]:
        """
        Fetch all entities from states_meta with their most recent attributes.
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
        Returns None if not found or not applicable.
        """
        if entity_id in self._attribute_cache:
            return self._attribute_cache[entity_id]

        with self.db.get_connection() as conn:
            # Find the most recent state with attributes for this entity
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

        # Sensors are generally low signal
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

        Returns: List of entity dicts with classification
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
