#!/usr/bin/env python3
"""
Automation Generator for HA-Autopilot Phase 2

Converts detected patterns into Home Assistant automation YAML configurations.
Generates safe, well-documented automations with proper formatting.
"""

import yaml
from typing import List, Dict, Any
from datetime import datetime
import re


class AutomationGenerator:
    """Generates Home Assistant automations from detected patterns"""

    def __init__(self):
        """Initialize automation generator"""
        self.generated_automations = []

        # Entities to exclude from automation (critical/safety systems)
        self.excluded_entities = {
            'climate.ecobee_main_floor', 'climate.ecobee_main_floor_2',
            'climate.ecobee_upstairs', 'climate.ecobee_upstairs_2',
            # Climate handled by existing automations
        }

    def generate_from_temporal(self, pattern) -> Dict[str, Any]:
        """Generate automation from temporal pattern"""

        # Skip excluded entities
        if pattern.entity_id in self.excluded_entities:
            return None

        # Generate unique ID
        auto_id = self._generate_id('temporal', pattern.entity_id, pattern.hour)

        # Build trigger based on pattern type
        if pattern.minute_range[0] == pattern.minute_range[1]:
            # Exact time
            trigger_time = f"{pattern.hour:02d}:{pattern.minute_range[0]:02d}:00"
            trigger = {
                'trigger': 'time',
                'at': trigger_time
            }
        else:
            # Time range - use midpoint
            avg_minute = (pattern.minute_range[0] + pattern.minute_range[1]) // 2
            trigger_time = f"{pattern.hour:02d}:{avg_minute:02d}:00"
            trigger = {
                'trigger': 'time',
                'at': trigger_time
            }

        # Build conditions based on day pattern
        conditions = []
        if pattern.pattern_type == 'weekday':
            conditions.append({
                'condition': 'time',
                'weekday': ['mon', 'tue', 'wed', 'thu', 'fri']
            })
        elif pattern.pattern_type == 'weekend':
            conditions.append({
                'condition': 'time',
                'weekday': ['sat', 'sun']
            })
        elif pattern.pattern_type == 'specific_day':
            day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            conditions.append({
                'condition': 'time',
                'weekday': [day_names[pattern.days_of_week[0]]]
            })

        # Build action
        domain, entity = pattern.entity_id.split('.', 1)

        # Determine service based on domain and target state
        service = self._get_service_for_state(domain, pattern.target_state)

        if service:
            action = {
                'action': f'{domain}.{service}',
                'target': {
                    'entity_id': pattern.entity_id
                }
            }

            # Add state data if needed
            if domain == 'cover' and pattern.target_state not in ['open', 'closed']:
                # Set position for covers
                try:
                    position = int(pattern.target_state)
                    action['data'] = {'position': position}
                except ValueError:
                    pass
        else:
            return None

        # Build automation
        automation = {
            'id': auto_id,
            'alias': f"[Autopilot] {self._friendly_name(pattern.entity_id)} at {trigger_time} {pattern.pattern_type}",
            'description': (
                f"Auto-generated from pattern detection. "
                f"{int(pattern.confidence*100)}% confidence based on {pattern.occurrences} occurrences. "
                f"Pattern: {pattern.description}"
            ),
            'triggers': [trigger],
            'actions': [action],
            'mode': 'single'
        }

        if conditions:
            automation['conditions'] = conditions

        return automation

    def generate_from_sequential(self, pattern) -> Dict[str, Any]:
        """Generate automation from sequential pattern"""

        # Skip excluded entities
        if pattern.action_entity in self.excluded_entities:
            return None

        # Generate unique ID
        auto_id = self._generate_id('sequential', pattern.trigger_entity, pattern.action_entity)

        # Build trigger
        trigger_domain = pattern.trigger_entity.split('.', 1)[0]

        # State trigger
        trigger = {
            'trigger': 'state',
            'entity_id': pattern.trigger_entity,
            'to': pattern.trigger_state
        }

        # Build conditions
        conditions = []

        # Optionally add timeout condition
        # (Home Assistant will wait up to time_window for conditions to be met)

        # Build action
        action_domain = pattern.action_entity.split('.', 1)[0]
        service = self._get_service_for_state(action_domain, pattern.action_state)

        if not service:
            return None

        action = {
            'action': f'{action_domain}.{service}',
            'target': {
                'entity_id': pattern.action_entity
            }
        }

        # Add delay to match typical behavior
        delay_action = {
            'delay': {
                'seconds': int(pattern.avg_delay_seconds)
            }
        }

        # Build automation
        automation = {
            'id': auto_id,
            'alias': (
                f"[Autopilot] {self._friendly_name(pattern.action_entity)} "
                f"after {self._friendly_name(pattern.trigger_entity)}"
            ),
            'description': (
                f"Auto-generated from pattern detection. "
                f"{int(pattern.confidence*100)}% confidence based on {pattern.occurrences} occurrences. "
                f"Pattern: {pattern.description}"
            ),
            'triggers': [trigger],
            'actions': [delay_action, action],
            'mode': 'restart'  # Restart if triggered again
        }

        if conditions:
            automation['conditions'] = conditions

        return automation

    def generate_from_conditional(self, pattern) -> Dict[str, Any]:
        """Generate automation from conditional pattern"""

        # Skip excluded entities
        if pattern.action_entity in self.excluded_entities:
            return None

        # Generate unique ID
        auto_id = self._generate_id('conditional', pattern.action_entity, str(hash(str(pattern.conditions))))

        # Build trigger - state change of action entity
        # We'll use conditions to enforce the pattern
        trigger = {
            'trigger': 'state',
            'entity_id': pattern.action_entity,
            'to': pattern.action_state
        }

        # Build conditions from pattern
        conditions = []
        for cond in pattern.conditions:
            if cond['type'] == 'time':
                if 'hour' in cond:
                    if cond.get('operator') == '>=':
                        conditions.append({
                            'condition': 'time',
                            'after': f"{cond['hour']:02d}:00:00"
                        })
                    elif cond.get('operator') == '<':
                        conditions.append({
                            'condition': 'time',
                            'before': f"{cond['hour']:02d}:00:00"
                        })

            elif cond['type'] == 'sun':
                conditions.append({
                    'condition': 'sun',
                    'after': 'sunset' if cond['position'] == 'below_horizon' else 'sunrise'
                })

            elif cond['type'] == 'presence':
                if cond['condition'] == 'anyone_home':
                    # Check if any person is home
                    conditions.append({
                        'condition': 'state',
                        'entity_id': 'person.cgrossmeier',  # TODO: Make dynamic
                        'state': 'home'
                    })

            elif cond['type'] == 'state':
                conditions.append({
                    'condition': 'state',
                    'entity_id': cond['entity_id'],
                    'state': cond['state']
                })

        # For conditional patterns, we don't auto-generate automations
        # because they often represent correlations, not causations
        # Instead, return None or mark as "suggestion only"
        return None

    def _get_service_for_state(self, domain: str, target_state: str) -> str:
        """Determine the appropriate service call for a given domain and target state"""
        state_lower = target_state.lower()

        # Common services
        if state_lower == 'on':
            return 'turn_on'
        elif state_lower == 'off':
            return 'turn_off'
        elif domain == 'cover':
            if state_lower == 'open':
                return 'open_cover'
            elif state_lower == 'closed':
                return 'close_cover'
            else:
                # Assume it's a position
                return 'set_cover_position'
        elif domain == 'media_player':
            if state_lower == 'playing':
                return 'media_play'
            elif state_lower == 'paused':
                return 'media_pause'
            elif state_lower == 'idle':
                return 'media_stop'
        elif domain == 'climate':
            # Don't auto-generate climate automations
            return None
        elif domain == 'lock':
            if state_lower == 'locked':
                return 'lock'
            elif state_lower == 'unlocked':
                return 'unlock'

        # Default services
        if state_lower in ['on', 'open', 'playing', 'home']:
            return 'turn_on'
        elif state_lower in ['off', 'closed', 'idle', 'not_home']:
            return 'turn_off'

        return None

    def _friendly_name(self, entity_id: str) -> str:
        """Convert entity_id to friendly name"""
        return entity_id.replace('_', ' ').replace('.', ' ').title()

    def _generate_id(self, pattern_type: str, *args) -> str:
        """Generate unique automation ID"""
        # Create deterministic ID from pattern details
        import hashlib
        content = f"{pattern_type}_{'_'.join(str(a) for a in args)}"
        hash_str = hashlib.md5(content.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime('%Y%m%d')
        return f"autopilot_{pattern_type}_{timestamp}_{hash_str}"

    def generate_yaml(self, patterns_by_type: Dict[str, List]) -> str:
        """
        Generate YAML for all patterns

        Args:
            patterns_by_type: Dict with 'temporal', 'sequential', 'conditional' keys

        Returns:
            YAML string of automations
        """
        automations = []

        # Generate from temporal patterns
        for pattern in patterns_by_type.get('temporal', []):
            auto = self.generate_from_temporal(pattern)
            if auto:
                automations.append(auto)

        # Generate from sequential patterns
        for pattern in patterns_by_type.get('sequential', []):
            auto = self.generate_from_sequential(pattern)
            if auto:
                automations.append(auto)

        # Conditional patterns are suggestions only
        # They represent correlations that may need manual review

        if not automations:
            return "# No automations generated\n"

        # Convert to YAML with custom formatting
        yaml_str = self._format_yaml(automations)

        return yaml_str

    def _format_yaml(self, automations: List[Dict]) -> str:
        """Format automations as YAML with nice formatting"""

        # Custom YAML dumper for better formatting
        class CustomDumper(yaml.SafeDumper):
            pass

        def str_presenter(dumper, data):
            if '\n' in data:
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
            return dumper.represent_scalar('tag:yaml.org,2002:str', data)

        CustomDumper.add_representer(str, str_presenter)

        # Generate YAML
        yaml_output = yaml.dump(
            automations,
            Dumper=CustomDumper,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120
        )

        # Add header
        header = f"""# Auto-Generated Automations by HA-Autopilot Phase 2
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
#
# IMPORTANT: Review these automations before deploying!
# These are based on statistical pattern detection and may not capture
# all nuances of your preferences.
#
# Total automations: {len(automations)}
#

"""

        return header + yaml_output


if __name__ == '__main__':
    # Test automation generation
    from temporal_analyzer import TemporalPattern
    from sequential_analyzer import SequentialPattern

    # Create sample patterns
    temp_pattern = TemporalPattern(
        entity_id='light.office',
        target_state='on',
        hour=9,
        minute_range=(0, 5),
        days_of_week=[0, 1, 2, 3, 4],
        confidence=0.95,
        occurrences=20,
        total_opportunities=21,
        description='Test pattern',
        pattern_type='weekday'
    )

    seq_pattern = SequentialPattern(
        trigger_entity='binary_sensor.door_entry_ge_sensor_door',
        trigger_state='on',
        action_entity='light.hallway_main_lights_2',
        action_state='on',
        time_window_seconds=60,
        avg_delay_seconds=5.0,
        confidence=0.92,
        occurrences=18,
        total_opportunities=20,
        description='Test sequential pattern'
    )

    generator = AutomationGenerator()
    yaml_output = generator.generate_yaml({
        'temporal': [temp_pattern],
        'sequential': [seq_pattern],
        'conditional': []
    })

    print(yaml_output)
