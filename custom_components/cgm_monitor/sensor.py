"""Support for monitoring CGM (Continuous Glucose Monitor) sensor data."""

import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    STATE_OK,
    STATE_PROBLEM,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_DICT_OF_UNITS_OF_MEASUREMENT,
    ATTR_PROBLEM,
    ATTR_SENSORS,
    CONF_GLUCOSE_SENSOR,
    CONF_TREND_SENSOR,
    CONF_WARNING_HIGH,
    CONF_WARNING_LOW,
    DEFAULT_WARNING_HIGH,
    DEFAULT_WARNING_LOW,
    PROBLEM_NONE,
    READING_GLUCOSE,
    READING_TREND,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_GLUCOSE_SENSOR): cv.entity_id,
        vol.Optional(CONF_TREND_SENSOR): cv.entity_id,
        vol.Optional(CONF_WARNING_HIGH, default=DEFAULT_WARNING_HIGH): vol.Coerce(float),
        vol.Optional(CONF_WARNING_LOW, default=DEFAULT_WARNING_LOW): vol.Coerce(float),
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

    @callback
    def _state_changed_event(self, event: Event[EventStateChangedData]) -> None:
        """Handle sensor state change events."""
        self.state_changed(event.data["entity_id"], event.data["new_state"])

    @callback
    def state_changed(self, entity_id: str, new_state: State | None) -> None:
        """Update readings when a tracked sensor changes."""
        if new_state is None:
            return
        value = new_state.state
        _LOGGER.debug("Received callback from %s with value %s", entity_id, value)
        if value == STATE_UNKNOWN:
            return

        reading = self._sensormap[entity_id]
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
        result = []

        if self._glucose is not None:
            if self._glucose == STATE_UNAVAILABLE:
                result.append("glucose unavailable")
            else:
                warning_low = self._config[CONF_WARNING_LOW]
                warning_high = self._config[CONF_WARNING_HIGH]
                if self._glucose < warning_low:
                    result.append("glucose low")
                elif self._glucose > warning_high:
                    result.append("glucose high")

        if result:
            self._state = STATE_PROBLEM
            self._problems = ", ".join(result)
        else:
            self._state = STATE_OK
            self._problems = PROBLEM_NONE

        _LOGGER.debug("New data processed")
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to sensor state changes after being added to hass."""
        async_track_state_change_event(
            self.hass, list(self._sensormap), self._state_changed_event
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
            ATTR_SENSORS: self._readingmap,
            ATTR_DICT_OF_UNITS_OF_MEASUREMENT: self._unit_of_measurement,
            READING_GLUCOSE: self._glucose,
        }
        if self._trend is not None:
            attrib[READING_TREND] = self._trend
        return attrib
