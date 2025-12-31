#!/usr/bin/env python3
"""
run_extraction.py - Main extraction script for HA-Autopilot Phase 1
"""

import argparse
import logging
from datetime import datetime, timedelta
import sys

from database import DatabaseConnector
from entity_classifier import EntityClassifier
from extractor import StateExtractor
from context_builder import ContextBuilder
from noise_filter import NoiseFilter
from exporter import DataExporter


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def main():
    parser = argparse.ArgumentParser(description="Extract state changes from Home Assistant")
    parser.add_argument("--days", type=int, default=30, help="Days of history to extract")
    parser.add_argument("--db-url", type=str, default=None, help="Database URL (auto-detect if not specified)")
    parser.add_argument("--output-dir", type=str, default="/config/ha_autopilot/exports")
    parser.add_argument("--include-medium", action="store_true", help="Include medium-signal entities")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be extracted without running")

    args = parser.parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger("run_extraction")

    # Initialize components
    logger.info("Initializing extraction pipeline...")

    try:
        db = DatabaseConnector(db_url=args.db_url)
        stats = db.test_connection()
        logger.info(f"Connected to {stats['database_type']} database")
        logger.info(f"Total state records: {stats['total_states']:,}")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)

    # Classify entities
    classifier = EntityClassifier(db)

    if args.include_medium:
        entities = classifier.get_filtered_entities(min_signal="medium")
    else:
        entities = classifier.get_filtered_entities(min_signal="high")

    entity_ids = [e["entity_id"] for e in entities]
    logger.info(f"Selected {len(entity_ids)} entities for extraction")

    if args.dry_run:
        logger.info("Dry run - entities that would be extracted:")
        for entity in entities:
            logger.info(f"  {entity['entity_id']} ({entity['signal_level']})")
        return

    # Extract state changes
    extractor = StateExtractor(db)

    start_time = datetime.now() - timedelta(days=args.days)
    end_time = datetime.now()

    logger.info(f"Extracting state changes from {start_time} to {end_time}")

    raw_events = extractor.extract_state_changes(
        entity_ids,
        start_time=start_time,
        end_time=end_time
    )

    # Build context vectors
    logger.info("Building context vectors...")
    context_builder = ContextBuilder(extractor, entity_ids)
    enriched_events = list(context_builder.build_context_vectors(raw_events))

    logger.info(f"Built {len(enriched_events)} context vectors")

    # Apply noise filter
    logger.info("Applying noise filters...")
    noise_filter = NoiseFilter()
    filtered_events = noise_filter.filter_events(enriched_events)

    # Add derived features
    for event in filtered_events:
        context_builder.add_derived_features(event)

    # Export
    logger.info("Exporting data...")
    exporter = DataExporter(output_dir=args.output_dir)

    data_path = exporter.export_jsonl(filtered_events)

    entity_report = noise_filter.get_entity_report(enriched_events)
    metadata_path = exporter.export_metadata(filtered_events, entity_report)

    logger.info("Extraction complete!")
    logger.info(f"Data file: {data_path}")
    logger.info(f"Metadata: {metadata_path}")

    # Summary
    logger.info("")
    logger.info("=== Extraction Summary ===")
    logger.info(f"Time range: {args.days} days")
    logger.info(f"Entities monitored: {len(entity_ids)}")
    logger.info(f"Raw state changes: {len(enriched_events)}")
    logger.info(f"After filtering: {len(filtered_events)}")
    logger.info(f"Reduction: {100 * (1 - len(filtered_events)/len(enriched_events)):.1f}%")


if __name__ == "__main__":
    main()
