"""Constants for CGM Monitor."""

from typing import Final

DOMAIN: Final = "cgm_monitor"

# ── Source sensor reading keys ─────────────────────────────────────────────────

READING_GLUCOSE = "glucose"
READING_TREND = "trend"

# ── Configuration keys ────────────────────────────────────────────────────────

CONF_GLUCOSE_SENSOR = "glucose_sensor"
CONF_TREND_SENSOR = "trend_sensor"
CONF_CRITICAL_LOW_THRESHOLD = "critical_low_threshold"
CONF_VERY_LOW_THRESHOLD = "very_low_threshold"
CONF_LOW_THRESHOLD = "low_threshold"
CONF_HIGH_THRESHOLD = "high_threshold"
CONF_VERY_HIGH_THRESHOLD = "very_high_threshold"
CONF_PRIORITY_MAPPING_OVERRIDES = "priority_mapping_overrides"
CONF_HASS_CONFIG = "hass_config"

# ── Default threshold values (mg/dL) ──────────────────────────────────────────

DEFAULT_CRITICAL_LOW_THRESHOLD: Final = 40
DEFAULT_VERY_LOW_THRESHOLD: Final = 60
DEFAULT_LOW_THRESHOLD: Final = 80
DEFAULT_HIGH_THRESHOLD: Final = 140
DEFAULT_VERY_HIGH_THRESHOLD: Final = 180

# ── CGM state values ──────────────────────────────────────────────────────────

STATE_CRITICAL_LOW = "critical_low"
STATE_VERY_LOW = "very_low"
STATE_LOW = "low"
STATE_HIGH = "high"
STATE_VERY_HIGH = "very_high"

CGM_STATES: Final[list[str]] = [
    STATE_CRITICAL_LOW,
    STATE_VERY_LOW,
    STATE_LOW,
    "ok",
    STATE_HIGH,
    STATE_VERY_HIGH,
]

# ── Priority values ───────────────────────────────────────────────────────────

PRIORITY_CRITICAL = "critical"
PRIORITY_WARNING = "warning"
PRIORITY_NORMAL = "normal"

PRIORITY_STATES: Final[list[str]] = [PRIORITY_CRITICAL, PRIORITY_WARNING, PRIORITY_NORMAL]

# ── Miscellaneous ─────────────────────────────────────────────────────────────

UNIT_MG_DL: Final = "mg/dL"
NUMBERS_LOADED_KEY = f"{DOMAIN}_numbers_loaded"

# (conf_key, default, human-readable label)
THRESHOLD_DEFINITIONS: Final[list[tuple[str, float, str]]] = [
    (CONF_CRITICAL_LOW_THRESHOLD, DEFAULT_CRITICAL_LOW_THRESHOLD, "Critical Low Threshold"),
    (CONF_VERY_LOW_THRESHOLD, DEFAULT_VERY_LOW_THRESHOLD, "Very Low Threshold"),
    (CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD, "Low Threshold"),
    (CONF_HIGH_THRESHOLD, DEFAULT_HIGH_THRESHOLD, "High Threshold"),
    (CONF_VERY_HIGH_THRESHOLD, DEFAULT_VERY_HIGH_THRESHOLD, "Very High Threshold"),
]
