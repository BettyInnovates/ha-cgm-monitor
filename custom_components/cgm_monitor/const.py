"""Constants for CGM Monitor."""

from typing import Final

DOMAIN: Final = "cgm_monitor"

READING_GLUCOSE = "glucose"
READING_TREND = "trend"

CONF_GLUCOSE_SENSOR = "glucose_sensor"
CONF_TREND_SENSOR = "trend_sensor"
CONF_WARNING_HIGH = "warning_high"
CONF_WARNING_LOW = "warning_low"

DEFAULT_WARNING_HIGH = 180
DEFAULT_WARNING_LOW = 70

ATTR_PROBLEM = "problem"
ATTR_SENSORS = "sensors"
ATTR_DICT_OF_UNITS_OF_MEASUREMENT = "unit_of_measurement_dict"
PROBLEM_NONE = "none"
