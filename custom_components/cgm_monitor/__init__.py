"""CGM Monitor integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType

from .const import CONF_HASS_CONFIG, DOMAIN


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the CGM Monitor integration and register the reload service."""
    hass.data.setdefault(DOMAIN, {})[CONF_HASS_CONFIG] = config
    # Only reload the sensor platform — number entities persist their values across reloads.
    await async_setup_reload_service(hass, DOMAIN, ["sensor"])
    return True
