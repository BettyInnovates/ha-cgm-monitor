"""Datetime entity for CGM Monitor event date/time input."""

import datetime as py_dt

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util, slugify


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up CGM Monitor event datetime entity."""
    if discovery_info is None:
        return

    sensor_name = discovery_info[CONF_NAME]
    async_add_entities([CgmEventDateTimeInput(sensor_name)])


class CgmEventDateTimeInput(RestoreEntity, DateTimeEntity):
    """Datetime entity for selecting the date and time of a new CGM event."""

    _attr_should_poll = False

    def __init__(self, sensor_name: str) -> None:
        self._attr_name = f"{sensor_name} Event DateTime"
        self._attr_unique_id = f"{slugify(sensor_name)}_event_datetime"
        self._attr_native_value: py_dt.datetime = dt_util.now().replace(second=0, microsecond=0)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            if (parsed := dt_util.parse_datetime(last.state)) is not None:
                self._attr_native_value = parsed

    async def async_set_value(self, value: py_dt.datetime) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
