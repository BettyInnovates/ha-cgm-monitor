"""Select entities for CGM Monitor event form inputs."""

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .const import EVENT_TYPES, EVENT_UNITS


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up CGM Monitor event form select entities."""
    if discovery_info is None:
        return

    sensor_name = discovery_info[CONF_NAME]
    async_add_entities([
        CgmEventTypeSelect(sensor_name),
        CgmEventUnitSelect(sensor_name),
    ])


class CgmEventTypeSelect(RestoreEntity, SelectEntity):
    """Select entity for choosing the event type on the subject detail form."""

    _attr_should_poll = False
    _attr_options = EVENT_TYPES

    def __init__(self, sensor_name: str) -> None:
        self._attr_name = f"{sensor_name} Event Type"
        self._attr_unique_id = f"{slugify(sensor_name)}_event_type"
        self._attr_current_option = EVENT_TYPES[0]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            if last.state in self._attr_options:
                self._attr_current_option = last.state

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


class CgmEventUnitSelect(RestoreEntity, SelectEntity):
    """Select entity for choosing the event unit on the subject detail form."""

    _attr_should_poll = False
    _attr_options = EVENT_UNITS

    def __init__(self, sensor_name: str) -> None:
        self._attr_name = f"{sensor_name} Event Unit"
        self._attr_unique_id = f"{slugify(sensor_name)}_event_unit"
        self._attr_current_option = EVENT_UNITS[0]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            if last.state in self._attr_options:
                self._attr_current_option = last.state

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
