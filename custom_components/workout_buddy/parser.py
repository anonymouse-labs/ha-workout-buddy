"""Turn raw sensor attributes, event payloads and text into a Workout."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import math
import re
from typing import Any

from homeassistant.util import dt as dt_util

from .const import (
    CONF_DISTANCE_UNIT,
    CONF_DURATION_UNIT,
    CONF_ENERGY_UNIT,
)

_INVALID = {"", "unknown", "unavailable", "nan", "none", "null"}

# Factor to minutes / km / kcal
DURATION = {
    "s": 1 / 60, "sec": 1 / 60, "secs": 1 / 60, "second": 1 / 60, "seconds": 1 / 60,
    "min": 1, "mins": 1, "minute": 1, "minutes": 1, "m": 1,
    "h": 60, "hr": 60, "hrs": 60, "hour": 60, "hours": 60, "u": 60, "uur": 60,
}  # fmt: skip
DISTANCE = {
    "m": 0.001, "meter": 0.001, "meters": 0.001, "metre": 0.001, "metres": 0.001,
    "km": 1, "kilometer": 1, "kilometers": 1,
    "mi": 1.609344, "mile": 1.609344, "miles": 1.609344,
}  # fmt: skip
ENERGY = {
    "kcal": 1, "cal": 1, "kilocalories": 1,
    "kj": 1 / 4.184, "j": 1 / 4184,
}  # fmt: skip

_NUM = r"([-+]?\d+(?:[.,]\d+)?)"
_QTY = re.compile(rf"^\s*{_NUM}\s*([A-Za-z]*)\s*$")
_CLOCK = re.compile(r"^\s*(\d+):(\d{2})(?::(\d{2}))?\s*$")


def clean(value: Any) -> Any | None:
    """Return None for empty, unknown, unavailable or NaN values."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        if value.lower() in _INVALID:
            return None
    return value


def parse_quantity(value: Any, default_unit: str = "") -> tuple[float, str] | None:
    """Parse 12, '12,5' or '12.5 km' into (number, lowercase unit)."""
    value = clean(value)
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value), default_unit.lower()
    match = _QTY.match(str(value))
    if not match:
        return None
    return float(match[1].replace(",", ".")), (match[2] or default_unit).lower()


def convert(value: Any, default_unit: str, table: Mapping[str, float]) -> float | None:
    """Convert a value (with optional unit suffix) to the table's base unit."""
    if table is DURATION and isinstance(value, str) and (c := _CLOCK.match(value)):
        h, m, s = int(c[1]), int(c[2]), int(c[3] or 0)
        return round(h * 60 + m + s / 60, 4) if c[3] else float(h * 60 + m)
    quantity = parse_quantity(value, default_unit)
    if quantity is None or quantity[1] not in table:
        return None
    return round(quantity[0] * table[quantity[1]], 4)


def parse_dt(value: Any) -> datetime | None:
    """Parse ISO strings, datetimes and epoch seconds/milliseconds into UTC."""
    value = clean(value)
    if value is None:
        return None
    if isinstance(value, int | float) or re.fullmatch(r"\d{9,13}(\.\d+)?", str(value)):
        number = float(value)
        return datetime.fromtimestamp(number / 1000 if number > 1e11 else number, UTC)
    parsed = (
        value
        if isinstance(value, datetime)
        else dt_util.parse_datetime(str(value), raise_on_error=False)
    )
    return dt_util.as_utc(parsed) if parsed else None


def type_key(workout_type: str | None) -> str:
    """Group key for 'the same kind of workout'."""
    return (workout_type or "workout").strip().casefold()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@dataclass(frozen=True, slots=True)
class Workout:
    """A normalised workout: minutes, km, kcal, bpm."""

    type: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    duration: float | None = None
    distance: float | None = None
    kcal: float | None = None
    avg_hr: float | None = None
    max_hr: float | None = None

    @property
    def valid(self) -> bool:
        """A workout needs at least a start or one measurement."""
        return any(
            v is not None
            for v in (self.start, self.duration, self.distance, self.kcal)
        )

    @property
    def key(self) -> str:
        """Dedupe key: type + start, or a hash of the values when start is unknown."""
        if self.start:
            return f"{type_key(self.type)}|{int(self.start.timestamp())}"
        raw = "|".join(
            str(x)
            for x in (
                type_key(self.type),
                self.duration,
                self.distance,
                self.kcal,
                self.avg_hr,
                self.max_hr,
            )
        )
        return "h|" + hashlib.sha1(raw.encode()).hexdigest()[:16]  # noqa: S324

    @property
    def pace(self) -> float | None:
        """Minutes per km."""
        if self.duration and self.distance and self.distance > 0:
            return self.duration / self.distance
        return None

    def as_dict(self) -> dict[str, Any]:
        """Serialise for storage and entity attributes."""
        return {
            "type": self.type,
            "start": _iso(self.start),
            "end": _iso(self.end),
            "duration": self.duration,
            "distance": self.distance,
            "kcal": self.kcal,
            "avg_hr": self.avg_hr,
            "max_hr": self.max_hr,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Workout:
        """Restore from storage."""
        return cls(
            type=data.get("type"),
            start=parse_dt(data.get("start")),
            end=parse_dt(data.get("end")),
            duration=data.get("duration"),
            distance=data.get("distance"),
            kcal=data.get("kcal"),
            avg_hr=data.get("avg_hr"),
            max_hr=data.get("max_hr"),
        )


def from_mapping(data: Mapping[str, Any], cfg: Mapping[str, Any]) -> Workout | None:
    """Build a workout from attributes/payload using the source's field mapping."""

    def get(field: str) -> Any:
        key = cfg.get(f"map_{field}")
        return clean(data.get(key)) if key else None

    wtype = get("type")
    start, end = parse_dt(get("start")), parse_dt(get("end"))
    duration = convert(get("duration"), cfg.get(CONF_DURATION_UNIT, "min"), DURATION)
    if duration is None and start and end and end > start:
        duration = round((end - start).total_seconds() / 60, 4)
    workout = Workout(
        type=str(wtype) if wtype is not None else None,
        start=start,
        end=end,
        duration=duration,
        distance=convert(get("distance"), cfg.get(CONF_DISTANCE_UNIT, "km"), DISTANCE),
        kcal=convert(get("kcal"), cfg.get(CONF_ENERGY_UNIT, "kcal"), ENERGY),
        avg_hr=_number(get("avg_hr")),
        max_hr=_number(get("max_hr")),
    )
    return workout if workout.valid else None


def _number(value: Any) -> float | None:
    quantity = parse_quantity(value)
    return quantity[0] if quantity else None


_TEXT_SPLIT = re.compile(r"\s*[·•|;]\s*|,\s+|\s+[-–—]\s+")
_TEXT_FIELDS: tuple[tuple[str, str, Mapping[str, float] | None], ...] = (
    ("hr", r"(bpm)", None),
    ("kcal", r"(kcal|cal|kj)", ENERGY),
    ("duration", r"(h|hr|hrs|u|uur|min|mins|s|sec)", DURATION),
    ("distance", r"(km|mi|m)", DISTANCE),
)


def _classify(part: str) -> tuple[str, float] | None:
    if _CLOCK.match(part):
        return "duration", convert(part, "min", DURATION) or 0.0
    for name, units, table in _TEXT_FIELDS:
        if m := re.search(rf"{_NUM}\s*{units}\b", part, re.IGNORECASE):
            number = float(m[1].replace(",", "."))
            if table is None:
                return ("max_hr" if re.search(r"\bmax", part, re.I) else "avg_hr"), number
            return name, number * table[m[2].lower()]
    return None


def parse_text(text: Any) -> Workout | None:
    """Parse 'Outdoor Walk · 129 min · 10.52 km · 663 kcal · 97 bpm' tolerantly."""
    text = clean(text)
    if text is None:
        return None
    parts = [p.strip() for p in _TEXT_SPLIT.split(str(text)) if p.strip()]
    if not parts:
        return None
    wtype = parts.pop(0) if _classify(parts[0]) is None else None
    values: dict[str, float] = {}
    for part in parts:
        if (found := _classify(part)) is not None:
            values.setdefault(found[0], round(found[1], 4))
    workout = Workout(type=wtype, **values)
    return workout if workout.valid else None

