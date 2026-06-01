"""Text entity for CGM Monitor event note input."""

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up CGM Monitor event text entities."""
    if discovery_info is None:
        return

    sensor_name = discovery_info[CONF_NAME]
    async_add_entities([CgmEventInitialsText(sensor_name), CgmEventNoteText(sensor_name)])


class CgmEventInitialsText(RestoreEntity, TextEntity):
    """Text entity for entering initials (max 3 chars) on the event form."""

    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = 3
    _attr_should_poll = False

    def __init__(self, sensor_name: str) -> None:
        self._attr_name = f"{sensor_name} Event Initials"
        self._attr_unique_id = f"{slugify(sensor_name)}_event_initials"
        self._attr_native_value = ""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._attr_native_value = last.state or ""

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()


class CgmEventNoteText(RestoreEntity, TextEntity):
    """Text entity for entering a free-text note on the subject detail event form."""

    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = 255
    _attr_should_poll = False

    def __init__(self, sensor_name: str) -> None:
        self._attr_name = f"{sensor_name} Event Note"
        self._attr_unique_id = f"{slugify(sensor_name)}_event_note"
        self._attr_native_value = ""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._attr_native_value = last.state or ""

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
