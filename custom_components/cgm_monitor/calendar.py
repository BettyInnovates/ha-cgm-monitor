"""Calendar entity and event store for CGM Monitor subject events."""

import datetime as py_dt
import uuid

from homeassistant.components.calendar import CalendarEntity, CalendarEntityFeature, CalendarEvent
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CALENDARS_KEY,
    CONF_EVENT_DOSE,
    CONF_EVENT_END,
    CONF_EVENT_INITIALS,
    CONF_EVENT_NOTE,
    CONF_EVENT_START,
    CONF_EVENT_TYPE,
    CONF_EVENT_UID,
    CONF_EVENT_UNIT,
    DOMAIN,
    EVENT_TYPES,
    STORES_KEY,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the CGM Monitor calendar entity for a subject."""
    if discovery_info is None:
        return

    sensor_name = discovery_info[CONF_NAME]
    slug = slugify(sensor_name)

    stores: dict = hass.data.setdefault(DOMAIN, {}).setdefault(STORES_KEY, {})
    if sensor_name not in stores:
        store = CgmEventStore(hass, slug)
        await store.async_load()
        stores[sensor_name] = store

    entity = CgmCalendarEntity(sensor_name, slug, stores[sensor_name])
    hass.data[DOMAIN].setdefault(CALENDARS_KEY, {})[sensor_name] = entity
    async_add_entities([entity])


# ── Event store ────────────────────────────────────────────────────────────────


class CgmEventStore:
    """Persists CGM events for one subject using HA's storage helper."""

    def __init__(self, hass: HomeAssistant, slug: str) -> None:
        self._store: Store = Store(hass, version=1, key=f"cgm_monitor_{slug}_events")
        self._events: list[dict] = []

    @property
    def events(self) -> list[dict]:
        return self._events

    async def async_load(self) -> None:
        data = await self._store.async_load()
        self._events = (data or {}).get("events", [])

    async def async_add(self, event_data: dict) -> str:
        uid = str(uuid.uuid4())
        event_data[CONF_EVENT_UID] = uid
        self._events.append(event_data)
        await self._store.async_save({"events": self._events})
        return uid

    async def async_delete(self, uid: str) -> bool:
        before = len(self._events)
        self._events = [e for e in self._events if e.get(CONF_EVENT_UID) != uid]
        if len(self._events) < before:
            await self._store.async_save({"events": self._events})
            return True
        return False

    def get_events_in_range(
        self, start: py_dt.datetime, end: py_dt.datetime
    ) -> list[dict]:
        result = []
        for e in self._events:
            try:
                event_start = py_dt.datetime.fromisoformat(e[CONF_EVENT_START])
                if not event_start.tzinfo:
                    event_start = dt_util.as_local(event_start)
                if start <= event_start <= end:
                    result.append(e)
            except (KeyError, ValueError):
                pass
        return sorted(result, key=lambda e: e[CONF_EVENT_START])


# ── Calendar entity ────────────────────────────────────────────────────────────


class CgmCalendarEntity(CalendarEntity):
    """One calendar per CGM subject, backed by CgmEventStore."""

    _attr_should_poll = False
    _attr_supported_features = CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT

    def __init__(self, sensor_name: str, slug: str, store: CgmEventStore) -> None:
        self._sensor_name = sensor_name
        self._store = store
        self._attr_name = f"{sensor_name} Events"
        self._attr_unique_id = f"{slug}_events"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event, or the most recent past event."""
        now = dt_util.now()
        future: list[dict] = []
        past: list[dict] = []
        for e in self._store.events:
            try:
                start = py_dt.datetime.fromisoformat(e[CONF_EVENT_START])
                if not start.tzinfo:
                    start = dt_util.as_local(start)
                (future if start >= now else past).append(e)
            except (KeyError, ValueError, TypeError):
                pass
        if future:
            return self._to_calendar_event(min(future, key=lambda e: e[CONF_EVENT_START]))
        if past:
            return self._to_calendar_event(max(past, key=lambda e: e[CONF_EVENT_START]))
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: py_dt.datetime,
        end_date: py_dt.datetime,
    ) -> list[CalendarEvent]:
        return [
            self._to_calendar_event(e)
            for e in self._store.get_events_in_range(start_date, end_date)
        ]

    async def async_create_event(self, **kwargs) -> None:
        """Handle event creation from the HA calendar UI."""
        summary = kwargs.get("summary", "Custom")
        event_type = summary if summary in EVENT_TYPES else "Custom"
        start: py_dt.datetime = kwargs["dtstart"]
        end: py_dt.datetime = kwargs.get("dtend", start)
        event_data = {
            CONF_EVENT_START: start.isoformat(),
            CONF_EVENT_END: end.isoformat(),
            CONF_EVENT_TYPE: event_type,
            CONF_EVENT_INITIALS: "",
            CONF_EVENT_UNIT: "",
            CONF_EVENT_DOSE: None,
            CONF_EVENT_NOTE: kwargs.get("description", ""),
        }
        await self._store.async_add(event_data)
        self.async_write_ha_state()

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Handle event deletion from the HA calendar UI or service."""
        await self._store.async_delete(uid)
        self.async_write_ha_state()

    def _to_calendar_event(self, e: dict) -> CalendarEvent:
        parts = []
        if e.get(CONF_EVENT_INITIALS):
            parts.append(e[CONF_EVENT_INITIALS])
        if e.get(CONF_EVENT_DOSE) is not None:
            parts.append(f"{e[CONF_EVENT_DOSE]} {e.get(CONF_EVENT_UNIT, '')}".strip())
        if e.get(CONF_EVENT_NOTE):
            parts.append(e[CONF_EVENT_NOTE])
        description = " | ".join(parts) if parts else None

        start = py_dt.datetime.fromisoformat(e[CONF_EVENT_START])
        if not start.tzinfo:
            start = dt_util.as_local(start)
        end_iso = e.get(CONF_EVENT_END) or e[CONF_EVENT_START]
        end = py_dt.datetime.fromisoformat(end_iso)
        if not end.tzinfo:
            end = dt_util.as_local(end)

        return CalendarEvent(
            summary=e.get(CONF_EVENT_TYPE, "Custom"),
            start=start,
            end=end,
            description=description,
            uid=e.get(CONF_EVENT_UID),
        )
