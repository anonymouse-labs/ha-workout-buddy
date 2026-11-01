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


def test_daily_chart_parts() -> None:
    rows = {
        "Ruub": {"steps": 8420, "heart_rate": (52, 141), "resting_heart_rate": 63},
        "Demi": {"steps": 7903, "heart_rate": None, "resting_heart_rate": None},
    }
    hr = {"Ruub": [(h, 70 + h) for h in range(0, 20)], "Demi": []}
    steps = {"Ruub": [(h, h * 400) for h in range(0, 20)], "Demi": [(h, h * 300) for h in range(0, 20)]}
    numbers = _png(daily_chart(rows, None, "nl", "01-11"))
    one_curve = _png(daily_chart(rows, {"heart_rate": hr}, "nl", "01-11"))
    two_curves = _png(daily_chart(rows, {"heart_rate": hr, "steps": steps}, "nl", "01-11"))
    assert numbers.height < one_curve.height < two_curves.height
    only_curves = _png(daily_chart(rows, {"heart_rate": hr}, "nl", "01-11", ("curves",)))
    assert only_curves.height == one_curve.height - 2 * 78  # no number rows
    assert daily_chart(rows, {"heart_rate": hr}, "nl", "01-11", ()) == b""
    assert daily_chart({"A": {"steps": None}}) == b""


def test_workout_chart_parts() -> None:
    only_numbers = _png(workout_chart("W", "d", ENTRIES, CURVE, CURVE, "nl", ("numbers",)))
    everything = _png(workout_chart("W", "d", ENTRIES, CURVE, CURVE, "nl"))
    assert only_numbers.height < everything.height
    assert workout_chart("W", "d", ENTRIES, CURVE, CURVE, "nl", ()) == b""
