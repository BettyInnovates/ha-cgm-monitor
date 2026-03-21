"""Switch entity to enable/disable notifications per CGM Monitor subject."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME, STATE_ON
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
    """Set up the CGM Monitor notifications switch."""
    if discovery_info is None:
        return

    sensor_name = discovery_info[CONF_NAME]
    async_add_entities([CgmNotificationsSwitch(sensor_name)])


class CgmNotificationsSwitch(RestoreEntity, SwitchEntity):
    """Switch to enable or disable notifications for a CGM Monitor subject."""

    _attr_should_poll = False

    def __init__(self, sensor_name: str) -> None:
        self._attr_name = f"{sensor_name} Notifications"
        self._attr_unique_id = f"{slugify(sensor_name)}_notifications"
        self._attr_is_on = True

    async def async_added_to_hass(self) -> None:
        """Restore last state on startup."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == STATE_ON

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
