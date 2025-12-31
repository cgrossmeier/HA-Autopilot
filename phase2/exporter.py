"""
Data export for HA-Autopilot.
Writes cleaned datasets to disk.
"""

import json
import os
from datetime import datetime
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class DataExporter:
    """
    Exports processed state change data to files.

    Args:
        output_dir: Directory for export files
    """

    def __init__(self, output_dir: str = "/config/ha_autopilot/exports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export_jsonl(self,
                     events: List[Dict],
                     filename: str = None) -> str:
        """
        Export events to JSON Lines format.

        Args:
            events: List of context-enriched events
            filename: Output filename (default: auto-generated with timestamp)

        Returns: Path to exported file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"state_changes_{timestamp}.jsonl"

        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w") as f:
            for event in events:
                # Convert any non-serializable types
                clean_event = self._clean_for_json(event)
                f.write(json.dumps(clean_event) + "\n")

        logger.info(f"Exported {len(events)} events to {filepath}")
        return filepath

    def export_metadata(self,
                        events: List[Dict],
                        entity_stats: Dict = None) -> str:
        """
        Export metadata about the extraction.
        """
        metadata = {
            "export_timestamp": datetime.now().isoformat(),
            "event_count": len(events),
            "entity_count": len(set(e["entity_id"] for e in events)),
            "date_range": {
                "start": min(e["datetime"] for e in events) if events else None,
                "end": max(e["datetime"] for e in events) if events else None
            },
            "entities": list(set(e["entity_id"] for e in events)),
            "entity_stats": entity_stats or {}
        }

        filepath = os.path.join(self.output_dir, "export_metadata.json")
        with open(filepath, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Exported metadata to {filepath}")
        return filepath

    def _clean_for_json(self, obj):
        """Convert non-JSON-serializable types."""
        if isinstance(obj, dict):
            return {k: self._clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._clean_for_json(v) for v in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            return str(obj)

    def load_jsonl(self, filepath: str) -> List[Dict]:
        """
        Load events from a JSON Lines file.
        """
        events = []
        with open(filepath, "r") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events
