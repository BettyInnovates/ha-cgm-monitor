"""Constants for CGM Monitor."""

from typing import Final

DOMAIN: Final = "cgm_monitor"

READING_GLUCOSE = "glucose"
READING_TREND = "trend"

CONF_GLUCOSE_SENSOR = "glucose_sensor"
CONF_TREND_SENSOR = "trend_sensor"
CONF_CRITICAL_LOW_THRESHOLD = "critical_low_threshold"
CONF_VERY_LOW_THRESHOLD = "very_low_threshold"
CONF_LOW_THRESHOLD = "low_threshold"
CONF_HIGH_THRESHOLD = "high_threshold"
CONF_VERY_HIGH_THRESHOLD = "very_high_threshold"

DEFAULT_CRITICAL_LOW_THRESHOLD = 40
DEFAULT_VERY_LOW_THRESHOLD = 60
DEFAULT_LOW_THRESHOLD = 80
DEFAULT_HIGH_THRESHOLD = 140
DEFAULT_VERY_HIGH_THRESHOLD = 180

STATE_CRITICAL_LOW = "critical_low"
STATE_VERY_LOW = "very_low"
STATE_WARNING = "warning"
STATE_HIGH = "high"
STATE_VERY_HIGH = "very_high"

ATTR_PROBLEM = "problem"
ATTR_SENSORS = "sensors"
ATTR_DICT_OF_UNITS_OF_MEASUREMENT = "unit_of_measurement_dict"
PROBLEM_NONE = "none"
