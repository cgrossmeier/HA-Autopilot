“”“
HA Autopilot Pattern Recognition Component.
This component discovers behavioral patterns in Home Assistant state history
and prepares automation suggestions for Claude Code translation.
Integration with Phase 1:
- Reads from Phase 1 JSON exports
- Can also query database directly for real-time updates
- Uses Phase 1 entity classifications for filtering\
“”“

import logging
from datetime import timedelta
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
import homeassistant.util.dt as dt_util

from .const import (
DOMAIN,
MINING_TIME,
INCREMENTAL_MINING_INTERVAL,
)
from .pattern_engine import PatternEngine
from .pattern_storage import PatternStorage
_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema(
{

DOMAIN: vol.Schema({
vol.Optional(”export_dir”, default=”/config/ha_autopilot/exports”): cv.string,
vol.Optional(”min_support”, default=0.10): cv.small_float,
vol.Optional(”min_confidence”, default=0.75): cv.small_float,
vol.Optional(”mining_enabled”, default=True): cv.boolean,
})
},
   extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    
“”“
Set up the HA Autopilot component.
Lifecycle:
1. Initialize pattern storage (create tables if needed)
2. Create pattern engine instance
3. Register services
4. Schedule daily mining
5. Start incremental updates
Args:
hass: Home Assistant instance
config: Component configuration from configuration.yaml
Returns:
True if setup successful
“”“
_LOGGER.info(”Initializing HA Autopilot Pattern Recognition”)

# Get configuration
conf = config.get(DOMAIN, {})

# Initialize storage layer
try:
storage = PatternStorage(hass)
await hass.async_add_executor_job(storage.initialize_schema)
_LOGGER.info(”Pattern storage initialized”)
except Exception as e:
_LOGGER.error(f”Failed to initialize pattern storage: {e}”)
return False

# Create pattern engine
engine = PatternEngine(
hass,
storage,
export_dir=conf.get(”export_dir”),
min_support=conf.get(”min_support”),
min_confidence=conf.get(”min_confidence”)
)

# Store in hass.data for access by services
hass.data[DOMAIN] = {
“engine”: engine,
“storage”: storage,
“config”: conf,
}
# Register services
async def handle_discover_patterns(call: ServiceCall):
    
“”“Service to manually trigger pattern discovery.”“”
days = call.data.get(”days”, 30)
incremental = call.data.get(”incremental”, False)
_LOGGER.info(f”Manual pattern discovery triggered (days={days}, incremental={incremental})”)
try:
await hass.async_add_executor_job(
engine.discover_patterns,
days,
incremental
)
_LOGGER.info(”Pattern discovery completed”)
except Exception as e:
_LOGGER.error(f”Pattern discovery failed: {e}”)
async def handle_export_patterns(call: ServiceCall):

“”“Service to export patterns for Claude Code.”“”
try:
filepath = await hass.async_add_executor_job(engine.export_patterns)
_LOGGER.info(f”Patterns exported to {filepath}”)
except Exception as e:
_LOGGER.error(f”Pattern export failed: {e}”)
async def handle_clear_patterns(call: ServiceCall):

“”“Service to clear all discovered patterns.”“”
confirm = call.data.get(”confirm”, False)
if not confirm:
_LOGGER.warning(”Pattern clearing requires confirm=true”)
return
try:
await hass.async_add_executor_job(storage.clear_all_patterns)
_LOGGER.info(”All patterns cleared”)
except Exception as e:
_LOGGER.error(f”Pattern clearing failed: {e}”)
hass.services.async_register(
DOMAIN,
“discover_patterns”,
handle_discover_patterns,
schema=vol.Schema({
vol.Optional(”days”, default=30): cv.positive_int,
vol.Optional(”incremental”, default=False): cv.boolean,
})
)
hass.services.async_register(
DOMAIN,
“export_patterns”,
handle_export_patterns
)
hass.services.async_register(
DOMAIN,
“clear_patterns”,
handle_clear_patterns,
schema=vol.Schema({
vol.Required(”confirm”): cv.boolean,
})
)

# Schedule daily pattern mining if enabled
if conf.get(”mining_enabled”, True):
hour, minute, second = MINING_TIME.split(”:”)
async def daily_mining(now):

“”“Run daily pattern discovery.”“”
_LOGGER.info(”Starting scheduled daily pattern mining”)
await hass.async_add_executor_job(
engine.discover_patterns,
30, # 30 days of history
False # Full analysis
)
async_track_time_change(
hass,
daily_mining,
hour=int(hour),
minute=int(minute),
second=int(second)
)

_LOGGER.info(f”Scheduled daily pattern mining at {MINING_TIME}”)
_LOGGER.info(”HA Autopilot Pattern Recognition setup complete”)
return True
