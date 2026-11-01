"""Parser: three source types, units, invalid values."""

from datetime import UTC, datetime

import pytest

from custom_components.workout_buddy.parser import (
    Workout,
    clean,
    from_mapping,
    parse_text,
)

CFG = {
    "map_type": "kind",
    "map_start": "begin",
    "map_end": "stop",
    "map_duration": "dur",
    "map_distance": "dist",
    "map_kcal": "energy",
    "map_avg_hr": "hr",
    "map_max_hr": "hr_max",
}


def test_text_example() -> None:
    w = parse_text("Outdoor Walk · 129 min · 10.52 km · 663 kcal · 97 bpm")
    assert w == Workout(type="Outdoor Walk", duration=129, distance=10.52, kcal=663, avg_hr=97)


def test_text_variants() -> None:
    w = parse_text("Run | 1:05:30 | 10,5 km | 2300 kJ | max 180 bpm")
    assert w.type == "Run"
    assert w.duration == pytest.approx(65.5)
    assert w.distance == 10.5
    assert w.kcal == pytest.approx(549.7, abs=0.1)
    assert w.max_hr == 180 and w.avg_hr is None
    assert parse_text("5000 m, 30 min").distance == 5.0
    assert parse_text("Swim · 1 h") .duration == 60


@pytest.mark.parametrize("value", [None, "", "unknown", "unavailable", "NaN", "geen workout"])
def test_text_invalid(value) -> None:
    assert parse_text(value) is None


def test_mapping_units_and_start() -> None:
    data = {
        "kind": "Cycling",
        "begin": "2026-01-02T10:00:00+00:00",
        "dur": 3600,
        "dist": 20000,
        "energy": 2092,
        "hr": "130",
        "hr_max": "NaN",
    }
    cfg = {**CFG, "duration_unit": "s", "distance_unit": "m", "energy_unit": "kJ"}
    w = from_mapping(data, cfg)
    assert w.type == "Cycling"
    assert w.start == datetime(2026, 1, 2, 10, tzinfo=UTC)
    assert (w.duration, w.distance, w.kcal, w.avg_hr, w.max_hr) == (60, 20, 500, 130, None)


def test_mapping_miles_and_duration_from_start_end() -> None:
    data = {
        "begin": 1767348000,
        "stop": 1767348000 + 1800,
        "dist": "3.1 mi",
    }
    w = from_mapping(data, CFG)
    assert w.duration == 30
    assert w.distance == pytest.approx(4.989, abs=0.001)


def test_mapping_nothing_usable() -> None:
    assert from_mapping({"kind": "Run", "dist": "unavailable"}, CFG) is None
    assert from_mapping({}, CFG) is None


def test_clean() -> None:
    assert clean(float("nan")) is None
    assert clean(" Unknown ") is None
    assert clean(0) == 0


def test_key_dedupe() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    assert Workout(type="Run", start=start).key == Workout(type="run ", start=start, kcal=1).key
    assert Workout(type="Run", duration=5).key == Workout(type="Run", duration=5).key
    assert Workout(type="Run", duration=5).key != Workout(type="Run", duration=6).key
