#!/usr/bin/env python3
"""
HA-Autopilot Phase 2: Pattern Detection Runner

Main script that orchestrates the pattern detection pipeline:
1. Load Phase 1 data
2. Run temporal, sequential, and conditional analyzers
3. Generate automation suggestions
4. Create backup and install automations (if requested)
5. Generate reports

Usage:
    python run_pattern_detection.py                    # Full analysis with auto-install
    python run_pattern_detection.py --no-install      # Generate suggestions only
    python run_pattern_detection.py --dry-run         # Show what would be detected
"""

import json
import argparse
import glob
from datetime import datetime
from pathlib import Path
import shutil
import yaml

from temporal_analyzer import TemporalAnalyzer
from sequential_analyzer import SequentialAnalyzer
from conditional_analyzer import ConditionalAnalyzer
from automation_generator import AutomationGenerator


class PatternDetectionRunner:
    """Main runner for pattern detection pipeline"""

    def __init__(self, min_confidence: float = 0.90, auto_install: bool = True):
        """
        Initialize pattern detection runner

        Args:
            min_confidence: Minimum confidence threshold for patterns
            auto_install: Whether to automatically install automations
        """
        self.min_confidence = min_confidence
        self.auto_install = auto_install
        self.export_dir = Path('/config/ha_autopilot/exports')
        self.suggestions_dir = Path('/config/ha_autopilot/suggestions')
        self.backup_dir = Path('/config/ha_autopilot/backups')

        # Create directories
        self.suggestions_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)

    def load_latest_data(self):
        """Load the most recent Phase 1 export"""
        export_files = sorted(glob.glob(str(self.export_dir / 'state_changes_*.jsonl')))

        if not export_files:
            raise FileNotFoundError("No Phase 1 export files found. Run Phase 1 first.")

        latest_file = export_files[-1]
        print(f"📂 Loading data from: {Path(latest_file).name}")

        events = []
        with open(latest_file, 'r') as f:
            for line in f:
                events.append(json.loads(line))

        print(f"   Loaded {len(events)} events")

        return events

    def run_analysis(self, events):
        """Run all pattern analyzers"""
        print(f"\n{'='*80}")
        print(f"PATTERN DETECTION ANALYSIS")
        print(f"{'='*80}")
        print(f"Minimum confidence: {int(self.min_confidence*100)}%")
        print(f"Total events: {len(events)}")
        print(f"{'='*80}\n")

        # Run temporal analysis
        temporal_analyzer = TemporalAnalyzer(
            min_confidence=self.min_confidence,
            min_occurrences=5
        )
        temporal_patterns = temporal_analyzer.analyze(events)

        # Run sequential analysis
        sequential_analyzer = SequentialAnalyzer(
            min_confidence=self.min_confidence,
            min_occurrences=5,
            max_window=300  # 5 minutes
        )
        sequential_patterns = sequential_analyzer.analyze(events)

        # Run conditional analysis
        conditional_analyzer = ConditionalAnalyzer(
            min_confidence=self.min_confidence,
            min_occurrences=5
        )
        conditional_patterns = conditional_analyzer.analyze(events)

        return {
            'temporal': temporal_patterns,
            'sequential': sequential_patterns,
            'conditional': conditional_patterns
        }

    def generate_automations(self, patterns):
        """Generate automation YAML from patterns"""
        print(f"\n{'='*80}")
        print(f"GENERATING AUTOMATIONS")
        print(f"{'='*80}\n")

        generator = AutomationGenerator()
        yaml_content = generator.generate_yaml(patterns)

        # Save to suggestions directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        suggestions_file = self.suggestions_dir / f'automations_{timestamp}.yaml'

        with open(suggestions_file, 'w') as f:
            f.write(yaml_content)

        print(f"✓ Automation suggestions saved to: {suggestions_file.name}")

        # Count automations
        try:
            with open(suggestions_file, 'r') as f:
                automations = yaml.safe_load(f) or []
                automation_count = len(automations) if isinstance(automations, list) else 0
        except:
            automation_count = 0

        return suggestions_file, automation_count

    def create_backup(self):
        """Create backup of current automations.yaml"""
        automations_file = Path('/config/automations.yaml')

        if not automations_file.exists():
            print("⚠️  Warning: No automations.yaml found to backup")
            return None

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = self.backup_dir / f'automations_backup_{timestamp}.yaml'

        shutil.copy2(automations_file, backup_file)
        print(f"✓ Backup created: {backup_file.name}")

        return backup_file

    def install_automations(self, suggestions_file):
        """Install generated automations to automations.yaml"""
        print(f"\n{'='*80}")
        print(f"INSTALLING AUTOMATIONS")
        print(f"{'='*80}\n")

        # Create backup first
        backup_file = self.create_backup()

        # Load current automations
        automations_file = Path('/config/automations.yaml')
        current_automations = []

        if automations_file.exists():
            with open(automations_file, 'r') as f:
                content = f.read()
                if content.strip() and content.strip() != '{}':
                    current_automations = yaml.safe_load(content) or []

        # Load new automations
        with open(suggestions_file, 'r') as f:
            new_automations = yaml.safe_load(f) or []

        if not isinstance(new_automations, list):
            print("⚠️  Warning: Invalid automation format")
            return False

        # Get existing autopilot IDs to avoid duplicates
        existing_autopilot_ids = set()
        for auto in current_automations:
            if isinstance(auto, dict) and auto.get('id', '').startswith('autopilot_'):
                existing_autopilot_ids.add(auto['id'])

        # Filter out duplicates
        unique_new = []
        for auto in new_automations:
            if auto.get('id') not in existing_autopilot_ids:
                unique_new.append(auto)

        if not unique_new:
            print("ℹ️  No new automations to install (all already exist)")
            return True

        # Merge automations
        merged_automations = current_automations + unique_new

        # Save merged automations
        with open(automations_file, 'w') as f:
            yaml.dump(
                merged_automations,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=120
            )

        print(f"✓ Installed {len(unique_new)} new automations to {automations_file}")
        print(f"✓ Total automations in file: {len(merged_automations)}")
        print(f"\n⚠️  IMPORTANT: Reload automations in Home Assistant UI to activate!")
        print(f"   Go to: Settings → Automations → ⋮ → Reload Automations")

        return True

    def generate_report(self, patterns, suggestions_file, automation_count):
        """Generate comprehensive analysis report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = self.suggestions_dir / f'pattern_report_{timestamp}.md'

        with open(report_file, 'w') as f:
            f.write(f"# HA-Autopilot Phase 2: Pattern Detection Report\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Confidence Threshold**: {int(self.min_confidence*100)}%\n\n")
            f.write(f"---\n\n")

            # Summary
            total_patterns = (
                len(patterns['temporal']) +
                len(patterns['sequential']) +
                len(patterns['conditional'])
            )

            f.write(f"## Summary\n\n")
            f.write(f"- **Total Patterns Detected**: {total_patterns}\n")
            f.write(f"  - Temporal (time-based): {len(patterns['temporal'])}\n")
            f.write(f"  - Sequential (A→B): {len(patterns['sequential'])}\n")
            f.write(f"  - Conditional (if-then): {len(patterns['conditional'])}\n")
            f.write(f"- **Automations Generated**: {automation_count}\n")
            f.write(f"- **Suggestions File**: `{suggestions_file.name}`\n\n")

            # Temporal patterns
            if patterns['temporal']:
                f.write(f"## Temporal Patterns ({len(patterns['temporal'])})\n\n")
                f.write(f"Time-based patterns that occur regularly:\n\n")
                for i, p in enumerate(patterns['temporal'][:20], 1):
                    f.write(f"{i}. {p.description}\n")
                if len(patterns['temporal']) > 20:
                    f.write(f"\n... and {len(patterns['temporal']) - 20} more\n")
                f.write(f"\n")

            # Sequential patterns
            if patterns['sequential']:
                f.write(f"## Sequential Patterns ({len(patterns['sequential'])})\n\n")
                f.write(f"Event sequences where one action triggers another:\n\n")
                for i, p in enumerate(patterns['sequential'][:20], 1):
                    f.write(f"{i}. {p.description}\n")
                if len(patterns['sequential']) > 20:
                    f.write(f"\n... and {len(patterns['sequential']) - 20} more\n")
                f.write(f"\n")

            # Conditional patterns
            if patterns['conditional']:
                f.write(f"## Conditional Patterns ({len(patterns['conditional'])})\n\n")
                f.write(f"Patterns that occur under specific conditions:\n\n")
                for i, p in enumerate(patterns['conditional'][:20], 1):
                    f.write(f"{i}. {p.description}\n")
                if len(patterns['conditional']) > 20:
                    f.write(f"\n... and {len(patterns['conditional']) - 20} more\n")
                f.write(f"\n")

            # Instructions
            f.write(f"---\n\n")
            f.write(f"## Next Steps\n\n")
            f.write(f"1. **Review Automations**: Open `{suggestions_file.name}` and review each automation\n")
            f.write(f"2. **Test in UI**: Go to Settings → Automations in Home Assistant\n")
            if self.auto_install:
                f.write(f"3. **Reload**: Click ⋮ → Reload Automations to activate new automations\n")
                f.write(f"4. **Disable Unwanted**: Disable any automations you don't want\n")
                f.write(f"5. **Monitor**: Watch for unexpected behavior and adjust as needed\n")
            else:
                f.write(f"3. **Manual Install**: Copy desired automations to automations.yaml\n")
                f.write(f"4. **Reload**: Reload automations in Home Assistant UI\n")

            f.write(f"\n---\n\n")
            f.write(f"## Backup Information\n\n")
            if self.auto_install:
                f.write(f"A backup of your automations was created before installation.\n")
                f.write(f"Check `/config/ha_autopilot/backups/` for backups.\n")
            else:
                f.write(f"No backup created (automations not installed automatically).\n")

        print(f"\n✓ Pattern report saved to: {report_file.name}")
        return report_file

    def run(self, dry_run=False):
        """Run the complete pattern detection pipeline"""
        try:
            # Load data
            events = self.load_latest_data()

            # Run analysis
            patterns = self.run_analysis(events)

            total_patterns = (
                len(patterns['temporal']) +
                len(patterns['sequential']) +
                len(patterns['conditional'])
            )

            if total_patterns == 0:
                print("\n❌ No patterns detected with current confidence threshold.")
                print("   Try lowering the confidence threshold or gathering more data.")
                return

            # Generate automations
            suggestions_file, automation_count = self.generate_automations(patterns)

            if dry_run:
                print(f"\n{'='*80}")
                print(f"DRY RUN MODE - No automations installed")
                print(f"{'='*80}\n")
                print(f"✓ Would generate {automation_count} automations")
                print(f"✓ Review suggestions in: {suggestions_file}")
                return

            # Install automations if requested
            if self.auto_install and automation_count > 0:
                success = self.install_automations(suggestions_file)
                if not success:
                    print("\n⚠️  Installation failed - check suggestions file manually")

            # Generate report
            report_file = self.generate_report(patterns, suggestions_file, automation_count)

            # Final summary
            print(f"\n{'='*80}")
            print(f"PATTERN DETECTION COMPLETE")
            print(f"{'='*80}\n")
            print(f"✓ Patterns detected: {total_patterns}")
            print(f"✓ Automations generated: {automation_count}")
            print(f"✓ Suggestions: {suggestions_file.name}")
            print(f"✓ Report: {report_file.name}")

            if self.auto_install and automation_count > 0:
                print(f"\n⚡ REMEMBER TO RELOAD AUTOMATIONS IN HOME ASSISTANT UI!")

            print(f"\n{'='*80}\n")

        except Exception as e:
            print(f"\n❌ Error during pattern detection: {e}")
            import traceback
            traceback.print_exc()
            return


def main():
    parser = argparse.ArgumentParser(
        description='HA-Autopilot Phase 2: Pattern Detection'
    )
    parser.add_argument(
        '--confidence',
        type=float,
        default=0.90,
        help='Minimum confidence threshold (0.0-1.0), default: 0.90'
    )
    parser.add_argument(
        '--no-install',
        action='store_true',
        help='Generate suggestions only, do not install automations'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be detected without generating files'
    )

    args = parser.parse_args()

    runner = PatternDetectionRunner(
        min_confidence=args.confidence,
        auto_install=not args.no_install
    )

    runner.run(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
