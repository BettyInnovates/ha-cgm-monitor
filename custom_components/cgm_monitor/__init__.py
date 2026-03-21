"""CGM Monitor integration."""

import datetime
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CALENDARS_KEY,
    CONF_EVENT_DATE,
    CONF_EVENT_DOSE,
    CONF_EVENT_END,
    CONF_EVENT_NOTE,
    CONF_EVENT_START,
    CONF_EVENT_SUBJECT,
    CONF_EVENT_TIME,
    CONF_EVENT_TYPE,
    CONF_EVENT_UID,
    CONF_EVENT_UNIT,
    CONF_HASS_CONFIG,
    DOMAIN,
    EVENT_TYPES,
    EVENT_UNITS,
    STORES_KEY,
)

_LOGGER = logging.getLogger(__name__)

_ADD_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EVENT_SUBJECT): cv.string,
        vol.Optional(CONF_EVENT_DATE): cv.string,
        vol.Optional(CONF_EVENT_TIME): cv.string,
        vol.Required(CONF_EVENT_TYPE): vol.In(EVENT_TYPES),
        vol.Optional(CONF_EVENT_UNIT): vol.In(EVENT_UNITS),
        vol.Optional(CONF_EVENT_DOSE): vol.Coerce(float),
        vol.Optional(CONF_EVENT_NOTE, default=""): cv.string,
    }
)

_DELETE_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EVENT_SUBJECT): cv.string,
        vol.Required(CONF_EVENT_UID): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the CGM Monitor integration and register the reload service."""
    hass.data.setdefault(DOMAIN, {})[CONF_HASS_CONFIG] = config
    # Only reload the sensor platform — number entities persist their values across reloads.
    await async_setup_reload_service(hass, DOMAIN, ["sensor"])

    async def handle_add_event(call: ServiceCall) -> None:
        subject: str = call.data[CONF_EVENT_SUBJECT]
        stores: dict = hass.data.get(DOMAIN, {}).get(STORES_KEY, {})
        if subject not in stores:
            _LOGGER.error("CGM Monitor add_event: unknown subject '%s'", subject)
            return

        date_str = call.data.get(CONF_EVENT_DATE)
        time_str = call.data.get(CONF_EVENT_TIME)
        event_date = (
            datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
        )
        event_time = (
            datetime.time.fromisoformat(time_str) if time_str else datetime.time(12, 0)
        )
        start = dt_util.as_local(datetime.datetime.combine(event_date, event_time))
        event_data = {
            CONF_EVENT_START: start.isoformat(),
            CONF_EVENT_END: start.isoformat(),
            CONF_EVENT_TYPE: call.data[CONF_EVENT_TYPE],
            CONF_EVENT_UNIT: call.data.get(CONF_EVENT_UNIT, ""),
            CONF_EVENT_DOSE: call.data.get(CONF_EVENT_DOSE),
            CONF_EVENT_NOTE: call.data.get(CONF_EVENT_NOTE, ""),
        }
        await stores[subject].async_add(event_data)

        calendar = hass.data[DOMAIN].get(CALENDARS_KEY, {}).get(subject)
        if calendar:
            calendar.async_write_ha_state()

    async def handle_delete_event(call: ServiceCall) -> None:
        subject: str = call.data[CONF_EVENT_SUBJECT]
        uid: str = call.data[CONF_EVENT_UID]
        stores: dict = hass.data.get(DOMAIN, {}).get(STORES_KEY, {})
        if subject not in stores:
            _LOGGER.error("CGM Monitor delete_event: unknown subject '%s'", subject)
            return

        deleted = await stores[subject].async_delete(uid)
        if deleted:
            calendar = hass.data[DOMAIN].get(CALENDARS_KEY, {}).get(subject)
            if calendar:
                calendar.async_write_ha_state()
        else:
            _LOGGER.warning(
                "CGM Monitor delete_event: event '%s' not found for subject '%s'", uid, subject
            )

    hass.services.async_register(DOMAIN, "add_event", handle_add_event, schema=_ADD_EVENT_SCHEMA)
    hass.services.async_register(DOMAIN, "delete_event", handle_delete_event, schema=_DELETE_EVENT_SCHEMA)

    return True
