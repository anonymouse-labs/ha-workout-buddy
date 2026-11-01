"""Compare a workout with an earlier one (neutral differences only)."""

from __future__ import annotations

from collections.abc import Sequence
from statistics import fmean

from .parser import Workout

# distance km, duration min, pace s/km, kcal, avg_hr bpm
COMPARED = ("distance", "duration", "pace", "kcal", "avg_hr")


def _value(workout: Workout, field: str) -> float | None:
    if field == "pace":
        return workout.pace * 60 if workout.pace else None
    return getattr(workout, field)


def deltas(current: Workout, reference: Workout) -> dict[str, float]:
    """Difference current - reference; fields missing on either side are skipped."""
    result: dict[str, float] = {}
    for field in COMPARED:
        a, b = _value(current, field), _value(reference, field)
        if a is not None and b is not None:
            result[field] = a - b
    return result


def average(workouts: Sequence[Workout]) -> Workout:
    """Mean of the fields that are present, per field."""

    def mean(field: str) -> float | None:
        values = [v for w in workouts if (v := getattr(w, field)) is not None]
        return fmean(values) if values else None

    return Workout(
        type=workouts[0].type,
        duration=mean("duration"),
        distance=mean("distance"),
        kcal=mean("kcal"),
        avg_hr=mean("avg_hr"),
        max_hr=mean("max_hr"),
    )
