"""Number entities for CGM Monitor thresholds."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from homeassistant.util import slugify

from .const import THRESHOLD_DEFINITIONS


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up CGM Monitor threshold and event number entities."""
    if discovery_info is None:
        return

    sensor_name = discovery_info[CONF_NAME]
    entities = [
        CgmThresholdNumber(
            sensor_name,
            conf_key,
            label,
            discovery_info.get(conf_key, default),
        )
        for conf_key, default, label in THRESHOLD_DEFINITIONS
    ]
    entities.append(CgmEventDoseNumber(sensor_name))
    async_add_entities(entities)


class CgmThresholdNumber(RestoreEntity, NumberEntity):
    """A configurable threshold for a CGM Monitor sensor."""

    _attr_mode = NumberMode.BOX
    _attr_native_step = 1.0
    _attr_native_min_value = 20.0
    _attr_native_max_value = 600.0

    def __init__(
        self, sensor_name: str, conf_key: str, label: str, initial: float
    ) -> None:
        """Initialize the threshold number entity."""
        self._attr_name = f"{sensor_name} {label}"
        self._initial = initial
        self._attr_native_value = initial

    async def async_added_to_hass(self) -> None:
        """Restore last value on startup."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._attr_native_value = float(last_state.state)
            except (ValueError, TypeError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        """Update the threshold value."""
        self._attr_native_value = value
        self.async_write_ha_state()


class CgmEventDoseNumber(RestoreEntity, NumberEntity):
    """Number entity for entering an event dose on the subject detail form."""

    _attr_mode = NumberMode.BOX
    _attr_native_step = 0.5
    _attr_native_min_value = 0.0
    _attr_native_max_value = 100.0
    _attr_should_poll = False

    def __init__(self, sensor_name: str) -> None:
        self._attr_name = f"{sensor_name} Event Dose"
        self._attr_unique_id = f"{slugify(sensor_name)}_event_dose"
        self._attr_native_value = 0.0

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._attr_native_value = float(last_state.state)
            except (ValueError, TypeError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
