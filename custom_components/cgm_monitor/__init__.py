"""CGM Monitor integration."""

import datetime
import logging

import voluptuous as vol

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util, slugify

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
    NOTIFY_TITLE_CRITICAL,
    NOTIFY_TITLE_WARNING,
    PRIORITY_CRITICAL,
    PRIORITY_WARNING,
    STORES_KEY,
    UNIT_MG_DL,
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

_SEND_NOTIFICATION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EVENT_SUBJECT): cv.string,
        vol.Required("target"): cv.string,
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

        slug = slugify(subject)
        await hass.services.async_call("date", "set_value", {"entity_id": f"date.{slug}_event_date", "date": datetime.date.today().isoformat()})
        await hass.services.async_call("time", "set_value", {"entity_id": f"time.{slug}_event_time", "time": "12:00:00"})
        await hass.services.async_call("select", "select_option", {"entity_id": f"select.{slug}_event_type", "option": EVENT_TYPES[0]})
        await hass.services.async_call("select", "select_option", {"entity_id": f"select.{slug}_event_unit", "option": EVENT_UNITS[0]})
        await hass.services.async_call("number", "set_value", {"entity_id": f"number.{slug}_event_dose", "value": 0})
        await hass.services.async_call("text", "set_value", {"entity_id": f"text.{slug}_event_note", "value": ""})

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

    async def handle_send_notification(call: ServiceCall) -> None:
        subject: str = call.data[CONF_EVENT_SUBJECT]
        target: str = call.data["target"]

        slug = slugify(subject)
        priority_state = hass.states.get(f"sensor.{slug}_priority")
        glucose_state = hass.states.get(f"sensor.{slug}")
        cgm_state = hass.states.get(f"sensor.{slug}_state")
        trend_state = hass.states.get(f"sensor.{slug}_trend")

        raw_priority = priority_state.state if priority_state else None
        priority = (
            raw_priority
            if raw_priority in (PRIORITY_CRITICAL, PRIORITY_WARNING)
            else PRIORITY_CRITICAL if raw_priority in (STATE_UNAVAILABLE, STATE_UNKNOWN, None)
            else "normal"
        )
        glucose = (
            glucose_state.state
            if glucose_state and glucose_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
            else "N/A"
        )
        state_str = (
            cgm_state.state.replace("_", " ").title()
            if cgm_state and cgm_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
            else "Unknown"
        )
        trend_str = (
            trend_state.state.replace("_", " ").title()
            if trend_state and trend_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
            else "Unknown"
        )

        title = NOTIFY_TITLE_CRITICAL if priority == PRIORITY_CRITICAL else NOTIFY_TITLE_WARNING
        message = (
            f"{subject}: {glucose} {UNIT_MG_DL}, "
            f"State: {state_str}, Trend: {trend_str}, Priority: {priority.title()}"
        )
        service_data: dict = {"title": title, "message": message}
        if priority == PRIORITY_CRITICAL:
            service_data["data"] = {
                "push": {"sound": {"name": "default", "critical": 1, "volume": 1.0}},
                "ttl": 0,
                "priority": "high",
                "channel": "alarm_stream",
            }

        domain, service_name = ("notify", target) if "." not in target else target.split(".", 1)
        try:
            await hass.services.async_call(domain, service_name, service_data)
        except Exception as err:
            _LOGGER.error("CGM Monitor send_notification: failed to call %s.%s: %s", domain, service_name, err)

    hass.services.async_register(DOMAIN, "add_event", handle_add_event, schema=_ADD_EVENT_SCHEMA)
    hass.services.async_register(DOMAIN, "delete_event", handle_delete_event, schema=_DELETE_EVENT_SCHEMA)
    hass.services.async_register(DOMAIN, "send_notification", handle_send_notification, schema=_SEND_NOTIFICATION_SCHEMA)

    return True
