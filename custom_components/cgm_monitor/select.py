"""Select entity for choosing the active CGM subject in the detail view."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, SUBJECTS_KEY


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the CGM subject select entity."""
    if discovery_info is None:
        return
    async_add_entities([CgmSubjectSelect()])


class CgmSubjectSelect(RestoreEntity, SelectEntity):
    """Tracks which CGM subject is currently active in the detail view."""

    _attr_name = "CGM Selected Subject"
    _attr_unique_id = "cgm_selected_subject"
    _attr_should_poll = False
    _attr_options: list[str] = []
    _attr_current_option: str | None = None

    def __init__(self) -> None:
        self._restored_option: str | None = None

    async def async_added_to_hass(self) -> None:
        """Restore last selection and populate options once HA has fully started."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            self._restored_option = last_state.state
        async_at_start(self.hass, self._async_populate_options)

    async def _async_populate_options(self, hass: HomeAssistant) -> None:
        """Read all registered subjects from hass.data after all platforms have loaded."""
        subjects: list[dict] = hass.data.get(DOMAIN, {}).get(SUBJECTS_KEY, [])
        self._attr_options = [s["name"] for s in subjects]
        if self._restored_option in self._attr_options:
            self._attr_current_option = self._restored_option
        elif self._attr_options:
            self._attr_current_option = self._attr_options[0]
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
