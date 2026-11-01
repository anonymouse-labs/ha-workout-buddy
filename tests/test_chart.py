"""Charts render to valid PNGs and skip empty data."""

import io

from PIL import Image

from custom_components.workout_buddy.chart import daily_chart, workout_chart
from custom_components.workout_buddy.parser import Workout

ENTRIES = [
    ("12-10", Workout(duration=100, distance=8.1, avg_hr=104)),
    ("19-10", Workout(duration=110, distance=9.3, avg_hr=100)),
    ("26-10", Workout(duration=121, distance=9.32, kcal=650, avg_hr=100)),
    ("01-11", Workout(duration=129, distance=10.52, kcal=663, avg_hr=97)),
]
CURVE = [(m, 90 + m / 10) for m in range(0, 130, 5)]


def _png(data: bytes) -> Image.Image:
    assert data.startswith(b"\x89PNG")
    return Image.open(io.BytesIO(data))


def test_workout_chart_with_curve_and_history_is_taller() -> None:
    full = _png(workout_chart("Walk", "01-11", ENTRIES, CURVE, CURVE[:10], "nl"))
    no_curve = _png(workout_chart("Walk", "01-11", ENTRIES, (), (), "nl"))
    assert full.width == 900 and full.height > no_curve.height


def test_workout_chart_first_workout_has_only_numbers() -> None:
    img = _png(workout_chart("Walk", "01-11", ENTRIES[-1:], (), (), "en"))
    assert img.height < 260  # no curve, no bars


def test_workout_chart_nothing_to_show() -> None:
    assert workout_chart("x", "y", [("a", Workout(type="Run"))]) == b""


def test_daily_chart() -> None:
    rows = {
        "Ruub": {"steps": 8420, "distance": 6.1, "heart_rate": 73, "resting_heart_rate": 63},
        "Demi": {"steps": 7903, "distance": 5.4, "heart_rate": 65, "resting_heart_rate": None},
    }
    day = {"Ruub": [(h, 70 + h) for h in range(0, 20)], "Demi": []}
    with_curve = _png(daily_chart(rows, day, "nl", "01-11"))
    without = _png(daily_chart(rows, None, "nl", "01-11"))
    assert with_curve.height > without.height
    assert daily_chart({"A": {"steps": None}}) == b""
