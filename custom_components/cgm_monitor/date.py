"""Date input entity for CGM Monitor event form."""

import datetime

from homeassistant.components.date import DateEntity
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
    """Set up the CGM Monitor date entity for a subject."""
    if discovery_info is None:
        return

    sensor_name = discovery_info[CONF_NAME]
    slug = slugify(sensor_name)
    async_add_entities([CgmEventDateInput(sensor_name, slug)])


class CgmEventDateInput(RestoreEntity, DateEntity):
    """Date picker for the CGM event form. Defaults to today."""

    _attr_should_poll = False

    def __init__(self, sensor_name: str, slug: str) -> None:
        self._attr_name = f"{sensor_name} Event Date"
        self._attr_unique_id = f"{slug}_event_date"
        self._attr_native_value: datetime.date | None = None

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        if last and last.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_native_value = datetime.date.fromisoformat(last.state)
                return
            except ValueError:
                pass
        self._attr_native_value = datetime.date.today()

    async def async_set_value(self, value: datetime.date) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
