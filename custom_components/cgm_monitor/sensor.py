"""Support for monitoring CGM (Continuous Glucose Monitor) sensor data."""

import logging
from pathlib import Path

import voluptuous as vol
import yaml

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    STATE_OK,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .const import (
    ATTR_DICT_OF_UNITS_OF_MEASUREMENT,
    ATTR_PRIORITY,
    ATTR_PROBLEM,
    ATTR_SENSORS,
    CONF_CRITICAL_LOW_THRESHOLD,
    CONF_GLUCOSE_SENSOR,
    CONF_HASS_CONFIG,
    CONF_HIGH_THRESHOLD,
    CONF_LOW_THRESHOLD,
    CONF_PRIORITY_MAPPING_OVERRIDES,
    CONF_TREND_SENSOR,
    CONF_VERY_HIGH_THRESHOLD,
    CONF_VERY_LOW_THRESHOLD,
    DEFAULT_CRITICAL_LOW_THRESHOLD,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_VERY_HIGH_THRESHOLD,
    DEFAULT_VERY_LOW_THRESHOLD,
    DOMAIN,
    NUMBERS_LOADED_KEY,
    PRIORITY_CRITICAL,
    PRIORITY_NORMAL,
    PRIORITY_WARNING,
    PROBLEM_NONE,
    READING_GLUCOSE,
    READING_TREND,
    STATE_CRITICAL_LOW,
    STATE_HIGH,
    STATE_VERY_HIGH,
    STATE_VERY_LOW,
    STATE_LOW,
    THRESHOLD_DEFINITIONS,
)

_LOGGER = logging.getLogger(__name__)

_PRIORITY_OVERRIDE_SCHEMA = vol.Schema(
    {
        vol.Required("state"): cv.string,
        vol.Required("trend"): cv.string,
        vol.Required("priority"): vol.In([PRIORITY_CRITICAL, PRIORITY_WARNING, PRIORITY_NORMAL]),
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_GLUCOSE_SENSOR): cv.entity_id,
        vol.Optional(CONF_TREND_SENSOR): cv.entity_id,
        vol.Optional(CONF_CRITICAL_LOW_THRESHOLD, default=DEFAULT_CRITICAL_LOW_THRESHOLD): vol.Coerce(float),
        vol.Optional(CONF_VERY_LOW_THRESHOLD, default=DEFAULT_VERY_LOW_THRESHOLD): vol.Coerce(float),
        vol.Optional(CONF_LOW_THRESHOLD, default=DEFAULT_LOW_THRESHOLD): vol.Coerce(float),
        vol.Optional(CONF_HIGH_THRESHOLD, default=DEFAULT_HIGH_THRESHOLD): vol.Coerce(float),
        vol.Optional(CONF_VERY_HIGH_THRESHOLD, default=DEFAULT_VERY_HIGH_THRESHOLD): vol.Coerce(float),
        vol.Optional(CONF_PRIORITY_MAPPING_OVERRIDES, default=[]): vol.All(
            cv.ensure_list, [_PRIORITY_OVERRIDE_SCHEMA]
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the CGM Monitor sensor platform."""
    async_add_entities([CgmMonitor(config)])

    # Load number entities for this sensor if not already created.
    # The guard prevents duplicate loading when the sensor platform is reloaded,
    # while still creating number entities for new sensors added to configuration.yaml.
    loaded: set[str] = hass.data.setdefault(NUMBERS_LOADED_KEY, set())
    sensor_name = config[CONF_NAME]
    if sensor_name not in loaded:
        loaded.add(sensor_name)
        hass_config = hass.data.get(DOMAIN, {}).get(CONF_HASS_CONFIG, {})
        hass.async_create_task(
            discovery.async_load_platform(hass, "number", DOMAIN, dict(config), hass_config)
        )


class CgmMonitor(SensorEntity):
    """Monitors CGM sensor data and checks glucose against warning thresholds."""

    _attr_should_poll = False

    def __init__(self, config: ConfigType) -> None:
        """Initialize the CGM Monitor."""
        self._config = config
        self._name = config[CONF_NAME]

        self._sensormap: dict[str, str] = {}
        self._readingmap: dict[str, str] = {}
        self._unit_of_measurement: dict[str, str] = {}

        self._sensormap[config[CONF_GLUCOSE_SENSOR]] = READING_GLUCOSE
        self._readingmap[READING_GLUCOSE] = config[CONF_GLUCOSE_SENSOR]

        if CONF_TREND_SENSOR in config:
            self._sensormap[config[CONF_TREND_SENSOR]] = READING_TREND
            self._readingmap[READING_TREND] = config[CONF_TREND_SENSOR]

        self._glucose: float | str | None = None
        self._trend: str | None = None
        self._state: str | None = None
        self._problems = PROBLEM_NONE
        self._priority: str = PRIORITY_NORMAL

        self._priority_map = self._build_priority_map(config.get(CONF_PRIORITY_MAPPING_OVERRIDES, []))

        name_slug = slugify(self._name)
        self._threshold_entity_ids = {
            f"number.{name_slug}_{conf_key}": (conf_key, default)
            for conf_key, default, _ in THRESHOLD_DEFINITIONS
        }

    @staticmethod
    def _build_priority_map(overrides: list[dict]) -> dict[tuple[str, str], str]:
        """Build a (state, trend) → priority lookup from defaults + config overrides."""
        defaults_path = Path(__file__).parent / "default-priority-mapping.yaml"
        try:
            with open(defaults_path) as f:
                data = yaml.safe_load(f)
            priority_map: dict[tuple[str, str], str] = {
                (entry["state"], entry["trend"]): entry["priority"]
                for entry in data.get("priority_mapping", [])
            }
        except Exception as err:
            _LOGGER.warning("Could not load default priority mapping: %s", err)
            priority_map = {}
        for override in overrides:
            priority_map[(override["state"], override["trend"])] = override["priority"]
        return priority_map

    @callback
    def _state_changed_event(self, event: Event[EventStateChangedData]) -> None:
        """Handle sensor state change events."""
        self.state_changed(event.data["entity_id"], event.data["new_state"])

    @callback
    def state_changed(self, entity_id: str, new_state: State | None) -> None:
        """Update readings when a tracked sensor changes."""
        reading = self._sensormap[entity_id]
        value = new_state.state if new_state is not None else None
        _LOGGER.debug("Received callback from %s with value %s", entity_id, value)

        # None (entity removed) and unknown are non-informative for the trend —
        # ignore them.  For glucose they signal a data gap and must be treated
        # as unavailable so that priority is escalated to critical.
        if value is None or value == STATE_UNKNOWN:
            if reading == READING_GLUCOSE:
                self._glucose = STATE_UNAVAILABLE
                self._update_state()
            return

        if reading == READING_GLUCOSE:
            if value != STATE_UNAVAILABLE:
                value = float(value)
            self._glucose = value
        elif reading == READING_TREND:
            self._trend = value
        else:
            raise HomeAssistantError(
                f"Unknown reading from sensor {entity_id}: {value}"
            )

        if ATTR_UNIT_OF_MEASUREMENT in new_state.attributes:
            self._unit_of_measurement[reading] = new_state.attributes[
                ATTR_UNIT_OF_MEASUREMENT
            ]

        self._update_state()

    def _update_state(self) -> None:
        """Update entity state based on current readings."""
        if self._glucose is not None:
            if self._glucose == STATE_UNAVAILABLE:
                self._state = STATE_UNAVAILABLE
                self._problems = "glucose unavailable"
                self._priority = PRIORITY_CRITICAL
                _LOGGER.debug("New data processed")
                self.async_write_ha_state()
                return
            else:
                critical_low = self._get_threshold(CONF_CRITICAL_LOW_THRESHOLD, DEFAULT_CRITICAL_LOW_THRESHOLD)
                very_low = self._get_threshold(CONF_VERY_LOW_THRESHOLD, DEFAULT_VERY_LOW_THRESHOLD)
                low = self._get_threshold(CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD)
                high = self._get_threshold(CONF_HIGH_THRESHOLD, DEFAULT_HIGH_THRESHOLD)
                very_high = self._get_threshold(CONF_VERY_HIGH_THRESHOLD, DEFAULT_VERY_HIGH_THRESHOLD)

                if self._glucose < critical_low:
                    self._state = STATE_CRITICAL_LOW
                elif self._glucose < very_low:
                    self._state = STATE_VERY_LOW
                elif self._glucose < low:
                    self._state = STATE_LOW
                elif self._glucose > very_high:
                    self._state = STATE_VERY_HIGH
                elif self._glucose > high:
                    self._state = STATE_HIGH
                else:
                    self._state = STATE_OK

        if self._state in (STATE_OK, None):
            self._problems = PROBLEM_NONE
        else:
            self._problems = self._state

        self._priority = self._priority_map.get((self._state, self._trend), PRIORITY_NORMAL)

        _LOGGER.debug("New data processed")
        self.async_write_ha_state()

    @callback
    def _threshold_changed_event(self, event: Event[EventStateChangedData]) -> None:
        """Re-evaluate state when a threshold number entity changes."""
        self._update_state()

    def _get_threshold(self, conf_key: str, default: float) -> float:
        """Read a threshold value from its number entity, falling back to config then default."""
        name_slug = slugify(self._name)
        entity_id = f"number.{name_slug}_{conf_key}"
        state = self.hass.states.get(entity_id)
        if state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                return float(state.state)
            except (ValueError, TypeError):
                pass
        return self._config.get(conf_key, default)

    async def async_added_to_hass(self) -> None:
        """Subscribe to sensor and threshold state changes after being added to hass."""
        async_track_state_change_event(
            self.hass, list(self._sensormap), self._state_changed_event
        )
        async_track_state_change_event(
            self.hass, list(self._threshold_entity_ids), self._threshold_changed_event
        )

        for entity_id in self._sensormap:
            if (state := self.hass.states.get(entity_id)) is not None:
                self.state_changed(entity_id, state)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> str | None:
        """Return the state of the entity."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity attributes including individual sensor readings."""
        attrib = {
            ATTR_PROBLEM: self._problems,
            ATTR_PRIORITY: self._priority,
            ATTR_SENSORS: self._readingmap,
            ATTR_DICT_OF_UNITS_OF_MEASUREMENT: self._unit_of_measurement,
            READING_GLUCOSE: self._glucose,
        }
        if self._trend is not None:
            attrib[READING_TREND] = self._trend
        return attrib
