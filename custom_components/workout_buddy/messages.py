"""Message texts (Dutch by default, English for English installs)."""

from __future__ import annotations

from collections.abc import Mapping

from .compare import deltas
from .parser import Workout

STR = {
    "nl": {
        "daily": "Dagoverzicht",
        "workout": "Workout van {person}: {type}",
        "default_type": "Workout",
        "first": "Eerste keer, nog geen vergelijking",
        "previous": "Vorige keer",
        "average": "Gemiddelde laatste {n}",
        "no_compare": "geen vergelijking mogelijk",
        "faster": "sneller",
        "slower": "langzamer",
        "same_pace": "gelijk",
        "avg_hr": "gem.",
        "avg_hr_long": "gem. hartslag",
        "steps": ("{v} stappen", "stappen -"),
        "distance": ("{v} km", "afstand -"),
        "heart_rate": ("hartslag {v} bpm", "hartslag -"),
        "resting_heart_rate": ("rust {v} bpm", "rust -"),
        "active_kcal": ("{v} kcal actief", "kcal actief -"),
        "sleep": ("slaap {v}", "slaap -"),
        "hour": "u",
        "pace": "tempo",
        "decimal": ",",
        "thousands": ".",
    },
    "en": {
        "daily": "Daily overview",
        "workout": "Workout of {person}: {type}",
        "default_type": "Workout",
        "first": "First time, nothing to compare with yet",
        "previous": "Last time",
        "average": "Average of last {n}",
        "no_compare": "no comparison possible",
        "faster": "faster",
        "slower": "slower",
        "same_pace": "equal",
        "avg_hr": "avg.",
        "avg_hr_long": "avg. heart rate",
        "steps": ("{v} steps", "steps -"),
        "distance": ("{v} km", "distance -"),
        "heart_rate": ("heart rate {v} bpm", "heart rate -"),
        "resting_heart_rate": ("resting {v} bpm", "resting -"),
        "active_kcal": ("{v} kcal active", "active kcal -"),
        "sleep": ("sleep {v}", "sleep -"),
        "hour": "h",
        "pace": "pace",
        "decimal": ".",
        "thousands": ",",
    },
}


def num(value: float, decimals: int, lang: str, *, signed: bool = False) -> str:
    """Locale number; signed deltas drop trailing zeros and show + or -."""
    s = STR[lang]
    text = f"{abs(value):,.{decimals}f}"
    if signed:
        text = text.rstrip("0").rstrip(".") if "." in text else text
    text = text.replace(",", "\0").replace(".", s["decimal"]).replace("\0", s["thousands"])
    if not signed:
        return ("-" if value < 0 else "") + text
    if text in ("0", ""):
        return "0"
    return ("-" if value < 0 else "+") + text


def _sleep(minutes: float, lang: str) -> str:
    h, m = divmod(round(minutes), 60)
    return f"{h} {STR[lang]['hour']} {m} min"


def daily_line(name: str, values: Mapping[str, float | None], lang: str) -> str:
    """'Name: 8.420 stappen, 6,1 km, hartslag 73 bpm, rust -'. Missing values show '-'."""
    parts = []
    for component, value in values.items():
        template, missing = STR[lang][component]
        if value is None:
            parts.append(missing)
        elif component == "distance":
            parts.append(template.format(v=num(value, 1, lang)))
        elif component == "sleep":
            parts.append(template.format(v=_sleep(value, lang)))
        else:
            parts.append(template.format(v=num(value, 0, lang)))
    return f"{name}: " + ", ".join(parts)


def daily_message(lines: list[str], lang: str) -> tuple[str, str]:
    return STR[lang]["daily"], "\n".join(lines)


def _facts(w: Workout, lang: str) -> str:
    s = STR[lang]
    parts = []
    if w.duration is not None:
        parts.append(f"{num(w.duration, 0, lang)} min")
    if w.distance is not None:
        parts.append(f"{num(w.distance, 2, lang)} km")
    if w.kcal is not None:
        parts.append(f"{num(w.kcal, 0, lang)} kcal")
    if w.avg_hr is not None:
        parts.append(f"{s['avg_hr']} {num(w.avg_hr, 0, lang)} bpm")
    if w.max_hr is not None:
        parts.append(f"max {num(w.max_hr, 0, lang)} bpm")
    return ", ".join(parts)


def _delta_line(label: str, current: Workout, reference: Workout, lang: str) -> str:
    s = STR[lang]
    d = deltas(current, reference)
    parts = []
    if "distance" in d:
        parts.append(f"{num(d['distance'], 2, lang, signed=True)} km")
    if "duration" in d:
        parts.append(f"{num(d['duration'], 0, lang, signed=True)} min")
    if "pace" in d:
        secs = round(d["pace"])
        word = s["same_pace"] if secs == 0 else s["faster"] if secs < 0 else s["slower"]
        parts.append(
            f"{s['pace']} {word}"
            if secs == 0
            else f"{s['pace']} {abs(secs)} s/km {word}"
        )
    if "kcal" in d:
        parts.append(f"{num(d['kcal'], 0, lang, signed=True)} kcal")
    if "avg_hr" in d:
        parts.append(f"{s['avg_hr_long']} {num(d['avg_hr'], 0, lang, signed=True)} bpm")
    return f"{label}: " + (", ".join(parts) or s["no_compare"])


def workout_message(
    person: str,
    current: Workout,
    previous: Workout | None,
    average: Workout | None,
    average_count: int,
    lang: str,
) -> tuple[str, str]:
    """Title and body for a finished workout."""
    s = STR[lang]
    title = s["workout"].format(person=person, type=current.type or s["default_type"])
    lines = [_facts(current, lang)]
    if previous is None:
        lines.append(s["first"])
    else:
        lines.append(_delta_line(s["previous"], current, previous, lang))
        if average is not None:
            lines.append(
                _delta_line(s["average"].format(n=average_count), current, average, lang)
            )
    return title, "\n".join(line for line in lines if line)
