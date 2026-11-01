"""Charts render to valid PNGs and skip empty data."""

import io

from PIL import Image

from custom_components.workout_buddy.chart import daily_chart, workout_chart
from custom_components.workout_buddy.parser import Workout

ENTRIES = [
    ("12-10", Workout(duration=100, distance=8.1, avg_hr=104)),
    ("19-10", Workout(duration=110, distance=9.3, avg_hr=100)),
    ("26-10", Workout(duration=121, distance=9.32, avg_hr=100)),
    ("01-11", Workout(duration=129, distance=10.52, avg_hr=97)),
]


def _png(data: bytes) -> Image.Image:
    assert data.startswith(b"\x89PNG")
    return Image.open(io.BytesIO(data))


def test_workout_chart_has_three_panels() -> None:
    img = _png(workout_chart("Workout van Ruub: Outdoor Walk", ENTRIES, "nl"))
    assert img.width == 20 + 3 * 270


def test_workout_chart_skips_missing_metrics() -> None:
    entries = [("a", Workout(duration=10)), ("b", Workout(duration=12))]
    assert workout_chart("x", entries) == b""  # nothing to compare
    entries = [("a", Workout(distance=1, duration=10)), ("b", Workout(distance=2, duration=12))]
    assert _png(workout_chart("x", entries)).width == 20 + 2 * 270  # distance + speed


def test_daily_chart_per_person() -> None:
    rows = {
        "Ruub": {"steps": 8420, "distance": 6.1, "heart_rate": 73, "resting_heart_rate": 63},
        "Demi": {"steps": 7903, "distance": 5.4, "heart_rate": 65, "resting_heart_rate": None},
    }
    img = _png(daily_chart(rows, "nl", "01-11"))
    assert img.width == 20 + 3 * 270 and img.height > 300  # four panels: two rows
    assert daily_chart({"A": {"steps": None}}, "nl") == b""
