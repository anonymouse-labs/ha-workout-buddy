"""Per-person sensors: last workout and last message."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import WorkoutBuddyConfigEntry
from .compare import deltas
from .entity import PersonEntity
from .parser import Workout


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WorkoutBuddyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    for person in manager.persons.values():
        async_add_entities(
            [LastWorkoutSensor(manager, person), LastMessageSensor(manager, person)],
            config_subentry_id=person.subentry_id,
        )


class LastWorkoutSensor(PersonEntity, SensorEntity):
    def __init__(self, manager, person) -> None:  # noqa: ANN001
        super().__init__(manager, person, "last_workout")

    @property
    def _record(self) -> dict[str, Any] | None:
        return self.manager.store.latest(self.person.name)

    @property
    def native_value(self) -> str | None:
        record = self._record
        return (record["workout"]["type"] or "Workout") if record else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if (record := self._record) is None:
            return None
        attrs: dict[str, Any] = {**record["workout"], "key": record["key"], "sent": record["sent"]}
        previous = self.manager.store.previous(self.person.name, record)
        if previous:
            attrs["vs_previous"] = deltas(
                Workout.from_dict(record["workout"]), Workout.from_dict(previous[-1]["workout"])
            )
        return attrs


class LastMessageSensor(PersonEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, manager, person) -> None:  # noqa: ANN001
        super().__init__(manager, person, "last_message")

    @property
    def _message(self) -> dict[str, str] | None:
        return self.manager.store.data["last_message"].get(self.person.name)

    @property
    def native_value(self) -> datetime | None:
        return dt_util.parse_datetime(self._message["time"]) if self._message else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return {"text": self._message["text"]} if self._message else None
