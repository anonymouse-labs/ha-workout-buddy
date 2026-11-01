"""Comparison and message text."""

from custom_components.workout_buddy.compare import average, deltas
from custom_components.workout_buddy.messages import daily_line, workout_message
from custom_components.workout_buddy.parser import Workout

PREV = Workout(type="Outdoor Walk", duration=121, distance=9.32, kcal=650, avg_hr=100)
CUR = Workout(type="Outdoor Walk", duration=129, distance=10.52, kcal=663, avg_hr=97)


def test_deltas() -> None:
    d = deltas(CUR, PREV)
    assert round(d["distance"], 2) == 1.2
    assert d["duration"] == 8
    assert d["avg_hr"] == -3
    assert d["pace"] < 0  # faster


def test_deltas_skip_missing_fields() -> None:
    d = deltas(CUR, Workout(duration=100))
    assert set(d) == {"duration"}


def test_average() -> None:
    avg = average([Workout(duration=10, distance=1), Workout(duration=20)])
    assert avg.duration == 15 and avg.distance == 1 and avg.kcal is None


def test_workout_message_nl() -> None:
    title, body = workout_message("Ruub", CUR, PREV, None, 0, "nl")
    assert title == "Workout van Ruub: Outdoor Walk"
    first, second = body.splitlines()
    assert first == "129 min, 10,52 km, 663 kcal, gem. 97 bpm"
    assert second.startswith("Vorige keer: +1,2 km, +8 min, tempo ")
    assert second.endswith("sneller, +13 kcal, gem. hartslag -3 bpm")


def test_workout_message_first_time_and_average() -> None:
    assert "Eerste keer" in workout_message("Ruub", CUR, None, None, 0, "nl")[1]
    body = workout_message("Ruub", CUR, PREV, average([PREV, PREV]), 2, "nl")[1]
    assert "Gemiddelde laatste 2:" in body


def test_daily_line_missing_values() -> None:
    line = daily_line(
        "Demi",
        {"steps": 7903, "distance": 5.43, "heart_rate": 65.2, "resting_heart_rate": None},
        "nl",
    )
    assert line == "Demi: 7.903 stappen, 5,4 km, hartslag 65 bpm, rust -"
    assert daily_line("X", {"steps": None, "sleep": 450}, "nl") == "X: stappen -, slaap 7 u 30 min"
    for bad in ("NaN", "None", "unknown"):
        assert bad not in line
