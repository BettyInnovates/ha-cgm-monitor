"""Constants for CGM Monitor."""

from typing import Final

DOMAIN: Final = "cgm_monitor"

# ── Source sensor reading keys ─────────────────────────────────────────────────

READING_GLUCOSE = "glucose"
READING_TREND = "trend"
READING_SENSOR_STATE = "sensor_state"

# ── Configuration keys ────────────────────────────────────────────────────────

CONF_GLUCOSE_SENSOR = "glucose_sensor"
CONF_TREND_SENSOR = "trend_sensor"
# Optional display label for reports (and, if ever wired up, the UI). Purely
# additive: the internal `name` stays the stable key for entity ids, .storage,
# lookups and the RAW archives. Absent → everything falls back to `name`.
CONF_DISPLAY_NAME = "display_name"
CONF_STATE_SENSOR = "state_sensor"  # optional: ESP CalibrationState byte; absent for Dexcom Share
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

# ── Sensor validity (ESP CalibrationState byte) ───────────────────────────────
# The ESP exposes the Dexcom CalibrationState as a decimal byte. Only state 6
# delivers usable glucose; state 2 is the warmup phase (no valid values, but
# expected and harmless). 4095 is the 12-bit "no value" sentinel and occurs both
# at warmup start and in error/stop states — never a real reading.
# See data_analysis/sensor_validity/SENSOR_STATE_CODES.md for the full enum.

SENSOR_STATE_VALID: Final = 6
SENSOR_STATE_WARMUP: Final = 2
GLUCOSE_SENTINEL: Final = 4095

# Derived categories so alarms/views can branch on a meaning instead of a raw
# byte. The raw code is always kept as the entity value; the category is only
# computed on top. Codes not listed here are treated as a general failure
# ("sensor dead / unknown") — fail safe. Extend the map as new codes are
# confirmed (see data_analysis/sensor_validity/SENSOR_STATE_CODES.md).

SENSOR_STATE_CAT_VALID = "valid"                # 6  — usable glucose
SENSOR_STATE_CAT_WARMUP = "warmup"              # 2  — warming up, values not yet trustworthy
SENSOR_STATE_CAT_TEMPORARY_ERROR = "temporary_error"  # 18 — temporary session failure
SENSOR_STATE_CAT_EXPIRED = "expired"            # 15 / 24 — session expired (sensor time ran out)
SENSOR_STATE_CAT_ERROR = "error"                # any other / unknown — general failure, sensor dead
SENSOR_STATE_CAT_DISCONNECTED = "disconnected"  # state source configured but no value — out of range / no internet / defective
SENSOR_STATE_CAT_NONE = "none"                  # no state source at all (Dexcom Share)

# Seconds any "no valid glucose" condition may stay a warning before it escalates
# to critical. Covers data gaps (Dexcom delivers empty / ESP brief loss),
# temporary_error (18) and disconnected (out of range) — all self-heal often, so
# a short dropout must not blast a critical immediately. 15 min aligns with
# Dexcom's own signal-loss handling. Exceptions: warmup (2) = no alarm,
# expired (15/24) = warning only, dead sensor 'error' (25/26/…) = immediate critical.
NO_VALUE_ESCALATION_SECONDS: Final = 15 * 60

# 15 = "Session Expired" per xDrip docs; 24 observed by us after the sensor's
# runtime elapsed. Both treated as expired — keep an eye on which actually shows.
SENSOR_STATE_CATEGORIES: Final[dict[int, str]] = {
    SENSOR_STATE_WARMUP: SENSOR_STATE_CAT_WARMUP,
    SENSOR_STATE_VALID: SENSOR_STATE_CAT_VALID,
    15: SENSOR_STATE_CAT_EXPIRED,
    18: SENSOR_STATE_CAT_TEMPORARY_ERROR,
    24: SENSOR_STATE_CAT_EXPIRED,
}

SENSOR_STATE_CATEGORY_VALUES: Final[list[str]] = [
    SENSOR_STATE_CAT_VALID,
    SENSOR_STATE_CAT_WARMUP,
    SENSOR_STATE_CAT_TEMPORARY_ERROR,
    SENSOR_STATE_CAT_EXPIRED,
    SENSOR_STATE_CAT_ERROR,
    SENSOR_STATE_CAT_DISCONNECTED,
    SENSOR_STATE_CAT_NONE,
]


def classify_sensor_state(sensor_state: str | int | None) -> str:
    """Map a raw CalibrationState byte to a category.

    None/empty (Dexcom Share, no source) → 'none'. Known codes map per
    SENSOR_STATE_CATEGORIES; everything else → 'error' (fail safe).
    """
    if sensor_state is None or sensor_state == "":
        return SENSOR_STATE_CAT_NONE
    try:
        code = int(float(sensor_state))
    except (ValueError, TypeError):
        return SENSOR_STATE_CAT_ERROR
    return SENSOR_STATE_CATEGORIES.get(code, SENSOR_STATE_CAT_ERROR)


def is_valid_reading(sensor_state: str | int | None, glucose: float | None) -> bool:
    """True if a reading is trustworthy.

    Source-independent: ESP delivers a sensor_state (only 6 is valid); Dexcom
    Share delivers none (sensor_state is None) → trusted by default. The 4095
    sentinel is never valid, regardless of source/state.
    """
    if glucose is None:
        return False
    try:
        if int(round(float(glucose))) == GLUCOSE_SENTINEL:
            return False
    except (ValueError, TypeError):
        return False
    if sensor_state is None or sensor_state == "":
        return True  # no state info (Dexcom Share) → trust the value
    try:
        return int(float(sensor_state)) == SENSOR_STATE_VALID
    except (ValueError, TypeError):
        return False


# ── Trend categories & numeric→category normalisation ─────────────────────────
# Some sources (Dexcom Share) deliver the trend already as a category string;
# others (ESP/BLE) deliver it as a numeric rate in mg/dL per minute. We normalise
# everything to a category so alarms, arrows and the priority mapping are
# source-independent. Bands follow Dexcom's arrow thresholds (±1/±2/±3 mg/dL/min);
# see data_analysis/trend_decoding/TREND_STRING_MAPPING.md for the derivation.

TREND_RISING_QUICKLY = "rising_quickly"

# (exclusive upper bound in mg/dL/min, category), ascending.
TREND_BANDS: Final[list[tuple[float, str]]] = [
    (-3.0, "falling_quickly"),
    (-2.0, "falling"),
    (-1.0, "falling_slightly"),
    (1.0, "steady"),
    (2.0, "rising_slightly"),
    (3.0, "rising"),
]


def classify_trend(value: str | float | None) -> str | None:
    """Normalise a trend reading to a category string.

    Category strings (Dexcom Share, also ``unavailable``/``unknown``) pass
    through unchanged. Numeric rates (mg/dL per minute, e.g. from an ESP) are
    mapped to Dexcom's arrow bands: |rate| < 1 steady, 1–2 slightly, 2–3 single,
    ≥ 3 quickly.
    """
    if value is None:
        return None
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return value
    for upper, category in TREND_BANDS:
        if rate < upper:
            return category
    return TREND_RISING_QUICKLY


# ── Priority values ───────────────────────────────────────────────────────────

PRIORITY_CRITICAL = "critical"
PRIORITY_WARNING = "warning"
PRIORITY_NORMAL = "normal"

PRIORITY_STATES: Final[list[str]] = [PRIORITY_CRITICAL, PRIORITY_WARNING, PRIORITY_NORMAL]

# ── Miscellaneous ─────────────────────────────────────────────────────────────

UNIT_MG_DL: Final = "mg/dL"
NUMBERS_LOADED_KEY = f"{DOMAIN}_numbers_loaded"
EVENT_SELECT_LOADED_KEY = f"{DOMAIN}_event_select_loaded"
CALENDAR_LOADED_KEY = f"{DOMAIN}_calendar_loaded"
TEXT_LOADED_KEY = f"{DOMAIN}_text_loaded"
DATE_LOADED_KEY = f"{DOMAIN}_date_loaded"
TIME_LOADED_KEY = f"{DOMAIN}_time_loaded"

# ── Subject events ─────────────────────────────────────────────────────────────

STORES_KEY = "stores"
CALENDARS_KEY = "calendars"
# Per-subject metadata for the report export (e.g. whether a state source exists).
# Keyed by subject_name, same key space as STORES_KEY.
SUBJECT_META_KEY = "subject_meta"

EVENT_TYPES: list[str] = ["Insulin", "Test Insulin", "Snack", "Meal", "Weighing", "Custom"]
EVENT_UNITS: list[str] = ["IU", "g Carbs", "kg", "—", "µL", "ml", "nmol/kg"]

# Default unit pre-selected when an event type is chosen on the form. Only a
# convenience pre-fill — the user can still switch to any other EVENT_UNITS
# entry afterwards (e.g. Insulin to µL for test insulin).
EVENT_TYPE_DEFAULT_UNIT: dict[str, str] = {
    "Insulin": "IU",
    "Test Insulin": "nmol/kg",
    "Snack": "g Carbs",
    "Meal": "g Carbs",
    "Weighing": "kg",
    "Custom": "—",
}

# Event types the customer receives in the MAIN events CSV. Everything else
# (Weighing, Custom, …) is kept only in the internal RAW events archive.
CUSTOMER_EVENT_TYPES: list[str] = ["Meal", "Snack", "Insulin", "Test Insulin"]

CONF_EVENT_SUBJECT = "subject"
CONF_EVENT_DATE = "date"
CONF_EVENT_TIME = "time"
CONF_EVENT_TYPE = "type"
CONF_EVENT_UNIT = "unit"
CONF_EVENT_DOSE = "dose"
CONF_EVENT_INITIALS = "initials"
CONF_EVENT_NOTE = "note"
CONF_EVENT_START = "start"   # internal storage key only
CONF_EVENT_END = "end"       # internal storage key only
CONF_EVENT_UID = "uid"

# ── Nextcloud upload configuration ───────────────────────────────────────────

CONF_NEXTCLOUD = "nextcloud"
CONF_NEXTCLOUD_URL = "url"
CONF_NEXTCLOUD_USER = "user"
CONF_NEXTCLOUD_PASSWORD = "password"
CONF_NEXTCLOUD_PATH = "path"
CONF_REPORT_ZIP_PASSWORD = "zip_password"

# ── upload_report service parameters ──────────────────────────────────────────

CONF_REPORT_SUBJECTS = "subjects"
CONF_REPORT_FILES = "files"
CONF_REPORT_FOLDER = "folder"
CONF_REPORT_SUFFIX = "suffix"

REPORT_FILE_GLUCOSE = "glucose"
REPORT_FILE_EVENTS = "events"
REPORT_FILE_FULL = "full"      # glucose + events merged
REPORT_FILE_REPORT = "report"  # combined HTML report
REPORT_FILE_RAW = "raw"        # every reading + sensor_state column (internal archive)
REPORT_FILE_EVENTS_RAW = "events_raw"  # every event + initials/uid (internal archive)

# Canonical order — also defines how the ZIP name tag is assembled.
REPORT_FILE_TYPES: list[str] = [
    REPORT_FILE_GLUCOSE,
    REPORT_FILE_EVENTS,
    REPORT_FILE_FULL,
    REPORT_FILE_REPORT,
    REPORT_FILE_RAW,
    REPORT_FILE_EVENTS_RAW,
]

# ── Notification configuration ────────────────────────────────────────────────

NOTIFY_TITLE_WARNING = "CGM Warning"
NOTIFY_TITLE_CRITICAL = "CGM Critical"

# (conf_key, default, human-readable label)
THRESHOLD_DEFINITIONS: Final[list[tuple[str, float, str]]] = [
    (CONF_CRITICAL_LOW_THRESHOLD, DEFAULT_CRITICAL_LOW_THRESHOLD, "Critical Low Threshold"),
    (CONF_VERY_LOW_THRESHOLD, DEFAULT_VERY_LOW_THRESHOLD, "Very Low Threshold"),
    (CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD, "Low Threshold"),
    (CONF_HIGH_THRESHOLD, DEFAULT_HIGH_THRESHOLD, "High Threshold"),
    (CONF_VERY_HIGH_THRESHOLD, DEFAULT_VERY_HIGH_THRESHOLD, "Very High Threshold"),
]
