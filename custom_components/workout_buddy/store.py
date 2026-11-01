"""Persistent workout history and message state."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MAX_ATTEMPTS
from .parser import Workout, type_key

Record = dict[str, Any]


def _sort_key(record: Record) -> str:
    return record["workout"].get("start") or record["received"]


class WorkoutStore:
    """Last N workouts per person and type, plus delivery state.

    Layout: workouts[person][type_key] = [record, ...] ordered oldest first.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry_id}")
        self.data: dict[str, Any] = {"workouts": {}, "last_message": {}}

    async def async_load(self) -> None:
        if loaded := await self._store.async_load():
            self.data = {"workouts": {}, "last_message": {}, **loaded}

    async def async_save(self) -> None:
        await self._store.async_save(self.data)

    def history(self, person: str, workout_type: str | None) -> list[Record]:
        return self.data["workouts"].get(person, {}).get(type_key(workout_type), [])

    def add(self, person: str, workout: Workout, size: int) -> Record | None:
        """Store a workout; return None when it is a duplicate."""
        records = (
            self.data["workouts"]
            .setdefault(person, {})
            .setdefault(type_key(workout.type), [])
        )
        if any(r["key"] == workout.key for r in records):
            return None
        record: Record = {
            "key": workout.key,
            "workout": workout.as_dict(),
            "received": dt_util.utcnow().isoformat(),
            "sent": False,
            "attempts": 0,
        }
        records.append(record)
        records.sort(key=_sort_key)
        # shortcut: dedupe only covers the kept history, a workout older than N re-sends
        del records[:-size]
        return record

    def find(self, person: str, key: str) -> Record | None:
        for by_type in self.data["workouts"].get(person, {}).values():
            for record in by_type:
                if record["key"] == key:
                    return record
        return None

    def latest(self, person: str) -> Record | None:
        records = [r for by in self.data["workouts"].get(person, {}).values() for r in by]
        return max(records, key=_sort_key, default=None)

    def unsent(self) -> list[tuple[str, Record]]:
        return [
            (person, record)
            for person, by_type in self.data["workouts"].items()
            for records in by_type.values()
            for record in records
            if not record["sent"] and record["attempts"] < MAX_ATTEMPTS
        ]

    def previous(self, person: str, record: Record) -> list[Record]:
        """Records of the same type before this one, oldest first."""
        records = self.history(person, record["workout"].get("type"))
        return records[: records.index(record)]

    def clear(self, person: str | None) -> None:
        if person is None:
            self.data = {"workouts": {}, "last_message": {}}
        else:
            self.data["workouts"].pop(person, None)
            self.data["last_message"].pop(person, None)
