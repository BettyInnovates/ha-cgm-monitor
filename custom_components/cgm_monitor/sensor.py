"""Support for monitoring CGM (Continuous Glucose Monitor) sensor data."""

import logging
from pathlib import Path

import voluptuous as vol
import yaml

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    STATE_OK,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .const import (
    ATTR_NOTIFICATION_SENT,
    CGM_STATES,
    CONF_CRITICAL_LOW_THRESHOLD,
    CONF_GLUCOSE_SENSOR,
    CONF_HASS_CONFIG,
    CONF_HIGH_THRESHOLD,
    CONF_LOW_THRESHOLD,
    CONF_NOTIFY_DEVICES,
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
    NOTIFY_TITLE_CRITICAL,
    NOTIFY_TITLE_WARNING,
    NUMBERS_LOADED_KEY,
    PRIORITY_CRITICAL,
    PRIORITY_NORMAL,
    PRIORITY_STATES,
    PRIORITY_WARNING,
    READING_GLUCOSE,
    READING_TREND,
    STATE_CRITICAL_LOW,
    STATE_HIGH,
    STATE_LOW,
    STATE_VERY_HIGH,
    STATE_VERY_LOW,
    SWITCHES_LOADED_KEY,
    THRESHOLD_DEFINITIONS,
    UNIT_MG_DL,
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
        vol.Required(CONF_TREND_SENSOR): cv.entity_id,
        vol.Optional(CONF_CRITICAL_LOW_THRESHOLD, default=DEFAULT_CRITICAL_LOW_THRESHOLD): vol.Coerce(float),
        vol.Optional(CONF_VERY_LOW_THRESHOLD, default=DEFAULT_VERY_LOW_THRESHOLD): vol.Coerce(float),
        vol.Optional(CONF_LOW_THRESHOLD, default=DEFAULT_LOW_THRESHOLD): vol.Coerce(float),
        vol.Optional(CONF_HIGH_THRESHOLD, default=DEFAULT_HIGH_THRESHOLD): vol.Coerce(float),
        vol.Optional(CONF_VERY_HIGH_THRESHOLD, default=DEFAULT_VERY_HIGH_THRESHOLD): vol.Coerce(float),
        vol.Optional(CONF_PRIORITY_MAPPING_OVERRIDES, default=[]): vol.All(
            cv.ensure_list, [_PRIORITY_OVERRIDE_SCHEMA]
        ),
        vol.Optional(CONF_NOTIFY_DEVICES, default=[]): vol.All(
            cv.ensure_list, [cv.entity_id]
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
    coordinator = CgmCoordinator(hass, config)

    entities: list[SensorEntity] = [
        CgmGlucoseSensor(coordinator),
        CgmStateSensor(coordinator),
        CgmPrioritySensor(coordinator),
        CgmTrendSensor(coordinator),
    ]

    for entity in entities:
        coordinator.register(entity)

    async_add_entities(entities)

    # Load number entities for this sensor if not already created.
    # The guard prevents duplicate loading when the sensor platform is reloaded,
    # while still creating number entities for new sensors added to configuration.yaml.
    sensor_name = config[CONF_NAME]
    hass_config = hass.data.get(DOMAIN, {}).get(CONF_HASS_CONFIG, {})

    loaded_numbers: set[str] = hass.data.setdefault(NUMBERS_LOADED_KEY, set())
    if sensor_name not in loaded_numbers:
        loaded_numbers.add(sensor_name)
        hass.async_create_task(
            discovery.async_load_platform(hass, "number", DOMAIN, dict(config), hass_config)
        )

    loaded_switches: set[str] = hass.data.setdefault(SWITCHES_LOADED_KEY, set())
    if sensor_name not in loaded_switches:
        loaded_switches.add(sensor_name)
        hass.async_create_task(
            discovery.async_load_platform(hass, "switch", DOMAIN, dict(config), hass_config)
        )


# ── Coordinator ────────────────────────────────────────────────────────────────


class CgmCoordinator:
    """Holds all CGM data, subscribes to source sensors, and notifies entities on change."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        self._hass = hass
        self._config = config
        self._name: str = config[CONF_NAME]
        self._name_slug: str = slugify(self._name)

        self._sensormap: dict[str, str] = {
            config[CONF_GLUCOSE_SENSOR]: READING_GLUCOSE,
            config[CONF_TREND_SENSOR]: READING_TREND,
        }

        self._threshold_entity_ids: set[str] = {
            f"number.{self._name_slug}_{conf_key}"
            for conf_key, _, _ in THRESHOLD_DEFINITIONS
        }

        self._glucose: float | None = None
        self._cgm_state: str | None = None
        self._trend: str | None = None
        self._priority: str = PRIORITY_NORMAL
        self._last_notified_priority: str | None = None

        self._priority_map = self._build_priority_map(
            config.get(CONF_PRIORITY_MAPPING_OVERRIDES, [])
        )

        self._entities: list[SensorEntity] = []
        self._setup_done = False

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def glucose(self) -> float | None:
        return self._glucose

    @property
    def cgm_state(self) -> str | None:
        return self._cgm_state

    @property
    def trend(self) -> str | None:
        return self._trend

    @property
    def priority(self) -> str:
        return self._priority

    @property
    def notification_sent(self) -> bool:
        return self._last_notified_priority == self._priority and self._priority != PRIORITY_NORMAL

    def register(self, entity: SensorEntity) -> None:
        """Register a dependent entity to be notified on data updates."""
        self._entities.append(entity)

    @callback
    def async_setup(self) -> None:
        """Subscribe to source sensors and fetch initial state. Called once after entities are added to hass."""
        if self._setup_done:
            return
        self._setup_done = True

        async_track_state_change_event(
            self._hass, list(self._sensormap), self._source_changed
        )
        async_track_state_change_event(
            self._hass, list(self._threshold_entity_ids), self._threshold_changed
        )

        for entity_id in self._sensormap:
            if (state := self._hass.states.get(entity_id)) is not None:
                self._process_source(entity_id, state)

    # ── Internal ───────────────────────────────────────────────────────────────

    @callback
    def _source_changed(self, event: Event[EventStateChangedData]) -> None:
        self._process_source(event.data["entity_id"], event.data["new_state"])

    @callback
    def _threshold_changed(self, event: Event[EventStateChangedData]) -> None:
        self._recalculate()

    def _process_source(self, entity_id: str, new_state: State | None) -> None:
        """Update internal readings from a source sensor state change."""
        reading = self._sensormap[entity_id]
        value = new_state.state if new_state is not None else None
        _LOGGER.debug("Received callback from %s with value %s", entity_id, value)

        # None (entity removed) and unknown are non-informative for trend.
        # For glucose they signal a data gap — treat as unavailable → critical priority.
        if value is None or value == STATE_UNKNOWN:
            if reading == READING_GLUCOSE:
                self._glucose = None
                self._cgm_state = None
                self._priority = PRIORITY_CRITICAL
                self._notify_entities()
            return

        if reading == READING_GLUCOSE:
            if value == STATE_UNAVAILABLE:
                self._glucose = None
                self._cgm_state = None
                self._priority = PRIORITY_CRITICAL
                self._notify_entities()
                return
            self._glucose = float(value)
        elif reading == READING_TREND:
            self._trend = value

        self._recalculate()

    def _recalculate(self) -> None:
        """Recompute cgm_state and priority from current readings."""
        if self._glucose is None:
            self._notify_entities()
            return

        critical_low = self._get_threshold(CONF_CRITICAL_LOW_THRESHOLD, DEFAULT_CRITICAL_LOW_THRESHOLD)
        very_low = self._get_threshold(CONF_VERY_LOW_THRESHOLD, DEFAULT_VERY_LOW_THRESHOLD)
        low = self._get_threshold(CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD)
        high = self._get_threshold(CONF_HIGH_THRESHOLD, DEFAULT_HIGH_THRESHOLD)
        very_high = self._get_threshold(CONF_VERY_HIGH_THRESHOLD, DEFAULT_VERY_HIGH_THRESHOLD)

        if self._glucose < critical_low:
            self._cgm_state = STATE_CRITICAL_LOW
        elif self._glucose < very_low:
            self._cgm_state = STATE_VERY_LOW
        elif self._glucose < low:
            self._cgm_state = STATE_LOW
        elif self._glucose > very_high:
            self._cgm_state = STATE_VERY_HIGH
        elif self._glucose > high:
            self._cgm_state = STATE_HIGH
        else:
            self._cgm_state = STATE_OK

        new_priority = self._priority_map.get(
            (self._cgm_state, self._trend), PRIORITY_NORMAL
        )

        self._priority = new_priority

        _LOGGER.debug("New data: glucose=%s state=%s priority=%s", self._glucose, self._cgm_state, self._priority)
        self._notify_entities()

    def _notify_entities(self) -> None:
        """Push current state to all registered entities that are ready."""
        for entity in self._entities:
            if entity.hass is not None:
                entity.async_write_ha_state()
        self._hass.async_create_task(self._async_maybe_notify())

    async def _async_maybe_notify(self) -> None:
        """Send a push notification if priority is active, not already sent, and enabled."""
        if self._priority == PRIORITY_NORMAL or self._last_notified_priority == self._priority:
            return

        notify_devices: list[str] = self._config.get(CONF_NOTIFY_DEVICES, [])
        if not notify_devices:
            return

        switch_id = f"switch.{self._name_slug}_notifications"
        switch_state = self._hass.states.get(switch_id)
        if switch_state is None or switch_state.state != STATE_ON:
            return

        title = NOTIFY_TITLE_CRITICAL if self._priority == PRIORITY_CRITICAL else NOTIFY_TITLE_WARNING
        message = self._build_notification_message()
        service_data: dict = {"title": title, "message": message}
        if self._priority == PRIORITY_CRITICAL:
            service_data["data"] = {
                "push": {"sound": {"name": "default", "critical": 1, "volume": 1.0}},
                "ttl": 0,
                "priority": "high",
                "channel": "alarm_stream",
            }

        for device_tracker_id in notify_devices:
            service_name = device_tracker_id.removeprefix("device_tracker.")
            service_name = f"mobile_app_{service_name}"
            try:
                await self._hass.services.async_call("notify", service_name, service_data)
            except Exception as err:
                _LOGGER.warning("Failed to notify via %s: %s", service_name, err)

        self._last_notified_priority = self._priority
        for entity in self._entities:
            if entity.hass is not None:
                entity.async_write_ha_state()

    def _build_notification_message(self) -> str:
        glucose_str = str(int(self._glucose)) if self._glucose is not None else "N/A"
        state_str = (self._cgm_state or "unknown").replace("_", " ").title()
        trend_str = (self._trend or "unknown").replace("_", " ").title()
        priority_str = self._priority.title()
        return (
            f"{self._name}: {glucose_str} {UNIT_MG_DL}, "
            f"State: {state_str}, Trend: {trend_str}, Priority: {priority_str}"
        )

    def _get_threshold(self, conf_key: str, default: float) -> float:
        """Read a threshold from its number entity, falling back to config then default."""
        entity_id = f"number.{self._name_slug}_{conf_key}"
        state = self._hass.states.get(entity_id)
        if state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                return float(state.state)
            except (ValueError, TypeError):
                pass
        return self._config.get(conf_key, default)

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


# ── Entity base class ──────────────────────────────────────────────────────────


class _CgmEntity(SensorEntity):
    """Base class for all CGM Monitor sensor entities."""

    _attr_should_poll = False

    def __init__(self, coordinator: CgmCoordinator) -> None:
        self._coordinator = coordinator

    async def async_added_to_hass(self) -> None:
        """Trigger coordinator subscription setup and write initial state."""
        self._coordinator.async_setup()
        self.async_write_ha_state()


# ── Concrete entities ──────────────────────────────────────────────────────────


class CgmGlucoseSensor(_CgmEntity):
    """Main sensor: current glucose reading in mg/dL."""

    _attr_native_unit_of_measurement = UNIT_MG_DL
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: CgmCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = coordinator.name
        self._attr_unique_id = f"{slugify(coordinator.name)}_glucose"

    @property
    def native_value(self) -> float | None:
        return self._coordinator.glucose


class CgmStateSensor(_CgmEntity):
    """Sensor reporting the CGM state category (critical_low, low, ok, high, …)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = CGM_STATES

    def __init__(self, coordinator: CgmCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{coordinator.name} State"
        self._attr_unique_id = f"{slugify(coordinator.name)}_state"

    @property
    def native_value(self) -> str | None:
        return self._coordinator.cgm_state


class CgmPrioritySensor(_CgmEntity):
    """Sensor reporting the alert priority derived from state + trend."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = PRIORITY_STATES

    def __init__(self, coordinator: CgmCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{coordinator.name} Priority"
        self._attr_unique_id = f"{slugify(coordinator.name)}_priority"

    @property
    def native_value(self) -> str:
        return self._coordinator.priority

    @property
    def extra_state_attributes(self) -> dict:
        return {ATTR_NOTIFICATION_SENT: self._coordinator.notification_sent}


class CgmTrendSensor(_CgmEntity):
    """Sensor mirroring the trend value from the configured trend source sensor."""

    def __init__(self, coordinator: CgmCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{coordinator.name} Trend"
        self._attr_unique_id = f"{slugify(coordinator.name)}_trend"

    @property
    def native_value(self) -> str | None:
        return self._coordinator.trend
