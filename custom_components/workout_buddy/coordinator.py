"""Listens to workout sources, sends daily and workout messages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from functools import partial
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .compare import average
from .const import (
    AVERAGE_OVER,
    COMPONENTS,
    CONF_COMPARE_AVG,
    CONF_COMPONENTS,
    CONF_DAILY_MODE,
    CONF_DAILY_TIME,
    CONF_DELAY,
    CONF_ENTITY_ID,
    CONF_EVENT_TYPE,
    CONF_HISTORY,
    CONF_JOINT_DEADLINE,
    CONF_JOINT_TIME,
    CONF_PERSON,
    CONF_RECIPIENT,
    CONF_SEND_SERVICE,
    CONF_SOURCE_TYPE,
    DAILY_JOINT,
    DAILY_JOINT_WAIT,
    DAILY_PER_PERSON,
    DEFAULT_DAILY_TIME,
    DEFAULT_DELAY,
    DEFAULT_HISTORY,
    DEFAULT_JOINT_DEADLINE,
    DEFAULT_JOINT_TIME,
    DEFAULT_SEND_SERVICE,
    DOMAIN,
    JOINT_POLL_MINUTES,
    MAX_ATTEMPTS,
    RETRY_MINUTES,
    SIGNAL_UPDATE,
    SOURCE_EVENT,
    SOURCE_TEXT,
    SUBENTRY_PERSON,
    SUBENTRY_SOURCE,
)
from .messages import daily_line, daily_message, workout_message
from .parser import (
    DISTANCE,
    DURATION,
    ENERGY,
    Workout,
    clean,
    convert,
    from_mapping,
    parse_quantity,
    parse_text,
)
from .store import Record, WorkoutStore

_LOGGER = logging.getLogger(__name__)

EMOJI_DAILY = "📊"
EMOJI_WORKOUT = "🏃"


@dataclass(slots=True)
class Person:
    name: str
    subentry_id: str
    daily_time: time
    components: list[str]
    entities: dict[str, str]


@dataclass(slots=True)
class Source:
    id: str
    name: str
    person: str
    type: str
    entity_id: str | None
    event_type: str | None
    cfg: Mapping[str, Any]


class WorkoutBuddy:
    """Owns config, store, listeners and sending."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store = WorkoutStore(hass, entry.entry_id)
        o = entry.options
        self.send_service: str = o.get(CONF_SEND_SERVICE) or DEFAULT_SEND_SERVICE
        self.recipient: str = (o.get(CONF_RECIPIENT) or "").strip()
        self.delay = int(o.get(CONF_DELAY, DEFAULT_DELAY))
        self.history_size = int(o.get(CONF_HISTORY, DEFAULT_HISTORY))
        self.compare_average: bool = o.get(CONF_COMPARE_AVG, False)
        self.daily_mode: str = o.get(CONF_DAILY_MODE, DAILY_PER_PERSON)
        self.joint_time = dt_util.parse_time(o.get(CONF_JOINT_TIME, DEFAULT_JOINT_TIME))
        self.joint_deadline = dt_util.parse_time(
            o.get(CONF_JOINT_DEADLINE, DEFAULT_JOINT_DEADLINE)
        )
        self.lang = "en" if hass.config.language.startswith("en") else "nl"
        self.persons: dict[str, Person] = {}
        self.sources: list[Source] = []
        self.last_event: dict[str, Mapping[str, Any]] = {}
        self._unsubs: list[Any] = []
        self._timers: dict[str, Any] = {}
        self._joint_pending = False
        self._sending: set[str] = set()
        self._read_subentries()

    # -- setup ---------------------------------------------------------------

    def _read_subentries(self) -> None:
        for sub in self.entry.subentries.values():
            d = sub.data
            if sub.subentry_type == SUBENTRY_PERSON:
                self.persons[sub.title] = Person(
                    name=sub.title,
                    subentry_id=sub.subentry_id,
                    daily_time=dt_util.parse_time(
                        d.get(CONF_DAILY_TIME, DEFAULT_DAILY_TIME)
                    ),
                    components=list(d.get(CONF_COMPONENTS, [])),
                    entities={
                        c: d[f"entity_{c}"] for c in COMPONENTS if d.get(f"entity_{c}")
                    },
                )
            elif sub.subentry_type == SUBENTRY_SOURCE:
                self.sources.append(
                    Source(
                        id=sub.subentry_id,
                        name=sub.title,
                        person=d[CONF_PERSON],
                        type=d[CONF_SOURCE_TYPE],
                        entity_id=d.get(CONF_ENTITY_ID),
                        event_type=d.get(CONF_EVENT_TYPE),
                        cfg=d,
                    )
                )
        orphans = [s for s in self.sources if s.person not in self.persons]
        for source in orphans:
            _LOGGER.warning(
                "Source %s belongs to unknown person %s and is ignored",
                source.name,
                source.person,
            )
        self.sources = [s for s in self.sources if s.person in self.persons]

    async def async_start(self) -> None:
        await self.store.async_load()
        hass = self.hass
        for source in self.sources:
            if source.type == SOURCE_EVENT and source.event_type:
                self._unsubs.append(
                    hass.bus.async_listen(
                        source.event_type, partial(self._on_event, source)
                    )
                )
            elif source.entity_id:
                self._unsubs.append(
                    async_track_state_change_event(
                        hass, [source.entity_id], partial(self._on_state, source)
                    )
                )
        if self.daily_mode == DAILY_PER_PERSON:
            for person in self.persons.values():
                self._unsubs.append(
                    async_track_time_change(
                        hass,
                        partial(self._daily_cb, person.name),
                        hour=person.daily_time.hour,
                        minute=person.daily_time.minute,
                        second=0,
                    )
                )
        else:
            self._unsubs.append(
                async_track_time_change(
                    hass,
                    self._joint_start,
                    hour=self.joint_time.hour,
                    minute=self.joint_time.minute,
                    second=0,
                )
            )
            if self.daily_mode == DAILY_JOINT_WAIT:
                self._unsubs.append(
                    async_track_time_interval(
                        hass,
                        self._joint_tick,
                        timedelta(minutes=JOINT_POLL_MINUTES),
                    )
                )
        self._unsubs.append(
            async_track_time_interval(
                hass, self._retry_unsent, timedelta(minutes=RETRY_MINUTES)
            )
        )

    @callback
    def _daily_cb(self, person: str, _now: datetime) -> None:
        self.hass.async_create_task(self.async_send_daily(person))

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        for cancel in self._timers.values():
            cancel()
        self._unsubs.clear()
        self._timers.clear()

    @callback
    def notify_entities(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(self.entry.entry_id))

    # -- workout sources -----------------------------------------------------

    @callback
    def _on_state(self, source: Source, event: Event) -> None:
        new: State | None = event.data.get("new_state")
        if new is None or clean(new.state) is None:
            return
        self._schedule(source)

    @callback
    def _on_event(self, source: Source, event: Event) -> None:
        self.last_event[source.name] = dict(event.data)
        self._schedule(source, dict(event.data))

    def _schedule(self, source: Source, payload: Mapping[str, Any] | None = None) -> None:
        """Debounce per source and process after the configured delay."""
        if cancel := self._timers.pop(source.id, None):
            cancel()

        async def process(_now: datetime | None = None) -> None:
            self._timers.pop(source.id, None)
            await self._process(source, payload)

        if self.delay <= 0:
            self.hass.async_create_task(process())
        else:
            self._timers[source.id] = async_call_later(self.hass, self.delay, process)

    def read_source(
        self, source: Source, payload: Mapping[str, Any] | None = None
    ) -> Workout | None:
        """Parse the source's current state (or the event payload)."""
        if source.type == SOURCE_EVENT:
            return from_mapping(payload or {}, source.cfg) if payload else None
        state = self.hass.states.get(source.entity_id or "")
        if state is None:
            return None
        if source.type == SOURCE_TEXT:
            return parse_text(state.state)
        return from_mapping({**state.attributes, "state": state.state}, source.cfg)

    async def _process(self, source: Source, payload: Mapping[str, Any] | None) -> None:
        workout = self.read_source(source, payload)
        if workout is None:
            _LOGGER.warning(
                "Source %s gave no usable workout. Check the field mapping, "
                "see the workout_buddy.dump_source service",
                source.name,
            )
            return
        record = self.store.add(source.person, workout, self.history_size)
        if record is None:
            _LOGGER.debug("Duplicate workout %s ignored", workout.key)
            return
        await self.store.async_save()
        self.notify_entities()
        await self.async_send_workout(source.person, record)

    # -- sending -------------------------------------------------------------

    async def _send(self, emoji: str, title: str, body: str, footer: str = "") -> bool:
        """Send through the configured channel. Never raises."""
        domain, _, name = self.send_service.partition(".")
        text = "\n".join(x for x in (f"{emoji} {title}", body, footer) if x)
        recipient = self.recipient
        if domain == "script":
            data: dict[str, Any] = {
                "emoji": emoji,
                "kop": title,
                "tekst": body,
                "voetnoot": footer,
            }
        elif self.send_service == "whatsapp_notifier.send_message":
            if not recipient:
                _LOGGER.error(
                    "No recipient (chat ID) configured for %s; set it in the "
                    "Workout Buddy options",
                    self.send_service,
                )
                return False
            data = {"message": text, "chat_id": recipient}
        elif self.send_service == "notify.send_message":
            if not recipient:
                _LOGGER.error(
                    "No notify entity configured as recipient for %s; set it in the "
                    "Workout Buddy options",
                    self.send_service,
                )
                return False
            data = {"entity_id": recipient, "message": text, "title": title}
        else:
            data = {"message": text, "title": title}
            if recipient:
                data["target"] = [recipient]
        if not domain or not name:
            _LOGGER.error("Invalid send service %r", self.send_service)
            return False
        try:
            await self.hass.services.async_call(domain, name, data, blocking=True)
        except Exception:  # noqa: BLE001 - a failing channel must never crash us
            _LOGGER.exception("Sending via %s failed", self.send_service)
            return False
        return True

    def _record_message(self, person: str, text: str) -> None:
        self.store.data["last_message"][person] = {
            "time": dt_util.utcnow().isoformat(),
            "text": text,
        }

    async def async_send_workout(self, person: str, record: Record) -> bool:
        """Send the summary for one stored workout; track attempts."""
        guard = f"{person}|{record['key']}"
        if guard in self._sending:
            return False
        self._sending.add(guard)
        try:
            return await self._send_workout(person, record)
        finally:
            self._sending.discard(guard)

    async def _send_workout(self, person: str, record: Record) -> bool:
        previous = [Workout.from_dict(r["workout"]) for r in self.store.previous(person, record)]
        recent = previous[-AVERAGE_OVER:]
        title, body = workout_message(
            person,
            Workout.from_dict(record["workout"]),
            previous[-1] if previous else None,
            average(recent) if self.compare_average and len(recent) > 1 else None,
            len(recent),
            self.lang,
        )
        ok = await self._send(EMOJI_WORKOUT, title, body)
        if ok:
            record["sent"] = True
            self._record_message(person, f"{title}\n{body}")
        else:
            record["attempts"] += 1
            _LOGGER.warning(
                "Workout %s of %s not sent (attempt %s/%s)",
                record["key"],
                person,
                record["attempts"],
                MAX_ATTEMPTS,
            )
        await self.store.async_save()
        self.notify_entities()
        return ok

    async def _retry_unsent(self, _now: datetime | None = None) -> None:
        for person, record in self.store.unsent():
            await self.async_send_workout(person, record)

    # -- daily overview ------------------------------------------------------

    def _read_component(self, component: str, entity_id: str) -> float | None:
        state = self.hass.states.get(entity_id)
        if state is None or clean(state.state) is None:
            return None
        unit = str(state.attributes.get("unit_of_measurement") or "")
        if component == "distance":
            return convert(state.state, unit or "km", DISTANCE)
        if component == "sleep":
            return convert(state.state, unit or "min", DURATION)
        if component == "active_kcal":
            return convert(state.state, unit or "kcal", ENERGY)
        quantity = parse_quantity(state.state)
        return quantity[0] if quantity else None

    def daily_values(self, person: Person) -> dict[str, float | None]:
        return {
            c: self._read_component(c, person.entities[c]) if c in person.entities else None
            for c in COMPONENTS
            if c in person.components
        }

    async def async_send_daily(self, person_name: str | None = None) -> bool:
        """Send one person's overview, or everyone's combined when None."""
        people = (
            [self.persons[person_name]] if person_name else list(self.persons.values())
        )
        if not people:
            return False
        lines = [daily_line(p.name, self.daily_values(p), self.lang) for p in people]
        title, body = daily_message(lines, self.lang)
        ok = await self._send(EMOJI_DAILY, title, body)
        if ok:
            for p in people:
                self._record_message(p.name, f"{title}\n{body}")
            await self.store.async_save()
            self.notify_entities()
        return ok

    # Dagsensoren resetten rond middernacht: joint_deadline is daarom een tijd op dezelfde dag.
    def _synced_today(self) -> bool:
        midnight = dt_util.start_of_local_day()
        for person in self.persons.values():
            for component in person.components:
                entity_id = person.entities.get(component)
                state = self.hass.states.get(entity_id) if entity_id else None
                if state is not None and max(state.last_updated, state.last_reported) < midnight:
                    return False
        return True

    async def _joint_start(self, _now: datetime) -> None:
        if self.daily_mode == DAILY_JOINT:
            await self.async_send_daily()
        else:
            self._joint_pending = True
            await self._joint_tick()

    async def _joint_tick(self, _now: datetime | None = None) -> None:
        if not self._joint_pending:
            return
        if self._synced_today() or dt_util.now().time() >= self.joint_deadline:
            self._joint_pending = False
            await self.async_send_daily()

    # -- diagnostics ---------------------------------------------------------

    def dump(self, source_name: str | None, entity_id: str | None) -> str:
        """Raw state/attributes (or last event payload) for the diagnose service."""
        lines: list[str] = []
        for source in self.sources:
            if source_name and source.name != source_name:
                continue
            if source.type == SOURCE_EVENT:
                lines.append(
                    f"[{source.name}] event {source.event_type}: "
                    f"{self.last_event.get(source.name, 'no event received yet')}"
                )
            else:
                lines.append(self._dump_entity(source.name, source.entity_id))
        if entity_id:
            lines.append(self._dump_entity(entity_id, entity_id))
        return "\n".join(lines) or "No source found"

    def _dump_entity(self, label: str, entity_id: str | None) -> str:
        state = self.hass.states.get(entity_id or "")
        if state is None:
            return f"[{label}] {entity_id}: does not exist"
        return (
            f"[{label}] {entity_id}: state={state.state!r} "
            f"last_updated={state.last_updated.isoformat()} "
            f"attributes={dict(state.attributes)}"
        )

    async def async_dump(self, source_name: str | None, entity_id: str | None) -> None:
        text = self.dump(source_name, entity_id)
        _LOGGER.warning("workout_buddy.dump_source\n%s", text)
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {"title": "Workout Buddy: dump_source", "message": text,
             "notification_id": f"{DOMAIN}_dump"},
        )  # fmt: skip

