"""PNG summaries: a workout with its heart rate curve against the last one, and the day."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import io
import math

from PIL import Image, ImageDraw, ImageFont

from .compare import deltas
from .messages import STR, num
from .parser import Workout

Series = Sequence[tuple[float, float]]  # (x, value)
RGB = tuple[int, int, int]

BG, FG, MUTED, GRID = (255, 255, 255), (33, 37, 41), (108, 117, 125), (228, 231, 235)
ACCENT, ACCENT_TINT, OTHER = (18, 150, 126), (221, 242, 237), (173, 181, 189)
PEOPLE: list[RGB] = [(18, 150, 126), (245, 159, 0), (73, 80, 214), (214, 51, 108)]
S = 2  # supersampling: PIL does not anti-alias, so draw big and scale down

TEXT = {
    "nl": {
        "now": "Deze keer", "last": "Vorige keer", "recent": "Laatste workouts",
        "note": "Onder elk cijfer: het verschil met de vorige keer",
        "distance": "Afstand", "time": "Tijd", "pace": "Tempo", "kcal": "Kcal", "avg_hr": "Gem. hartslag",
        "speed": "Snelheid (km/u)", "hr_bars": "Hartslag (bpm)", "dist_bars": "Afstand (km)",
        "hr_title": "Hartslag tijdens de workout", "hr_day": "Hartslag over de dag",
        "daily": "Dagoverzicht", "steps": "Stappen", "km": "Afstand (km)", "active_kcal": "Actieve kcal",
        "sleep": "Slaap", "heart_rate": "Hartslag", "resting_heart_rate": "Rust",
    },
    "en": {
        "now": "This time", "last": "Last time", "recent": "Recent workouts",
        "note": "Below each number: the difference from last time",
        "distance": "Distance", "time": "Time", "pace": "Pace", "kcal": "Kcal", "avg_hr": "Avg. heart rate",
        "speed": "Speed (km/h)", "hr_bars": "Heart rate (bpm)", "dist_bars": "Distance (km)",
        "hr_title": "Heart rate during the workout", "hr_day": "Heart rate over the day",
        "daily": "Daily overview", "steps": "Steps", "km": "Distance (km)", "active_kcal": "Active kcal",
        "sleep": "Sleep", "heart_rate": "Heart rate", "resting_heart_rate": "Resting",
    },
}  # fmt: skip


class Canvas:
    """Tiny drawing helper working in logical pixels."""

    def __init__(self, width: int, height: int) -> None:
        self.w, self.h = width, height
        self.img = Image.new("RGB", (width * S, height * S), BG)
        self.d = ImageDraw.Draw(self.img)

    def text(self, xy: tuple[float, float], s: str, size: int, fill: RGB = FG, anchor: str = "la") -> None:
        self.d.text((xy[0] * S, xy[1] * S), s, font=ImageFont.load_default(size=size * S), fill=fill, anchor=anchor)

    def line(self, pts: Sequence[tuple[float, float]], fill: RGB, width: float = 1) -> None:
        self.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=round(width * S), joint="curve")

    def rect(self, box: tuple[float, float, float, float], fill: RGB, radius: float = 0) -> None:
        self.d.rounded_rectangle([c * S for c in box], radius * S, fill=fill)

    def polygon(self, pts: Sequence[tuple[float, float]], fill: RGB) -> None:
        self.d.polygon([(x * S, y * S) for x, y in pts], fill=fill)

    def dot(self, x: float, y: float, r: float, fill: RGB) -> None:
        self.d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=fill)

    def png(self) -> bytes:
        out = io.BytesIO()
        self.img.resize((self.w, self.h), Image.LANCZOS).save(out, "PNG", optimize=True)
        return out.getvalue()


def _nice_step(span: float, target: int) -> float:
    raw = span / target
    for step in (1, 2, 5, 10, 15, 20, 30, 60, 120, 180, 240):
        if step >= raw:
            return step
    return math.ceil(raw)


def _legend(c: Canvas, right: float, y: float, items: Sequence[tuple[str, RGB]]) -> None:
    x = right
    for label, color in reversed(items):
        width = len(label) * 7.2
        x -= width
        c.text((x, y), label, 13, MUTED)
        c.dot(x - 10, y + 8, 5, color)
        x -= 34


def _line_chart(
    c: Canvas,
    box: tuple[float, float, float, float],
    lines: Sequence[tuple[Series, RGB, RGB | None]],
    x_ticks: Sequence[tuple[float, str]],
    x_range: tuple[float, float],
) -> None:
    """Lines (series, colour, fill tint) on shared axes with horizontal grid lines."""
    x0, y0, x1, y1 = box
    left, bottom = x0 + 40, y1 - 22
    values = [v for series, _, _ in lines for _, v in series]
    lo, hi = math.floor(min(values) / 5) * 5 - 5, math.ceil(max(values) / 5) * 5 + 5
    step = _nice_step(hi - lo, 4)
    lo = math.floor(lo / step) * step
    hi = math.ceil(hi / step) * step

    def px(x: float) -> float:
        return left + (x - x_range[0]) / ((x_range[1] - x_range[0]) or 1) * (x1 - left)

    def py(v: float) -> float:
        return bottom - (v - lo) / ((hi - lo) or 1) * (bottom - y0)

    v = lo
    while v <= hi:
        c.line([(left, py(v)), (x1, py(v))], GRID, 1)
        c.text((left - 8, py(v)), f"{v:.0f}", 12, MUTED, "rm")
        v += step
    for x, label in x_ticks:
        c.text((px(x), bottom + 6), label, 12, MUTED, "mt")
    for series, color, tint in reversed(lines):  # the first line is drawn last, on top
        if len(series) < 2:
            continue
        pts = [(px(x), py(v)) for x, v in series]
        if tint:
            c.polygon([(pts[0][0], bottom), *pts, (pts[-1][0], bottom)], tint)
        c.line(pts, color, 2.5)


def _pace(minutes_per_km: float) -> str:
    m, s = divmod(round(minutes_per_km * 60), 60)
    return f"{m}:{s:02d}"


def _kpis(current: Workout, previous: Workout | None, lang: str) -> list[tuple[str, str, str]]:
    t, s = TEXT[lang], STR[lang]
    d = deltas(current, previous) if previous else {}

    def delta(field: str, decimals: int, unit: str) -> str:
        return f"{num(d[field], decimals, lang, signed=True)} {unit}" if field in d else ""

    pace_delta = ""
    if "pace" in d:
        secs = round(d["pace"])
        pace_delta = (
            s["same_pace"] if secs == 0
            else f"{abs(secs)} s/km {s['faster'] if secs < 0 else s['slower']}"
        )  # fmt: skip
    rows = [
        (t["distance"], f"{num(current.distance, 2, lang)} km" if current.distance is not None else "-", delta("distance", 2, "km")),
        (t["time"], f"{num(current.duration, 0, lang)} min" if current.duration is not None else "-", delta("duration", 0, "min")),
        (t["pace"], f"{_pace(current.pace)} /km" if current.pace else "-", pace_delta),
        ("Kcal", f"{num(current.kcal, 0, lang)}" if current.kcal is not None else "-", delta("kcal", 0, "kcal")),
        (t["avg_hr"], f"{num(current.avg_hr, 0, lang)} bpm" if current.avg_hr is not None else "-", delta("avg_hr", 0, "bpm")),
    ]  # fmt: skip
    return [r for r in rows if r[1] != "-"]


def _bars(c: Canvas, x: float, y: float, w: float, h: float, title: str, bars: Sequence[tuple[str, float | None, RGB]], decimals: int, lang: str) -> None:
    c.text((x, y), title, 14, MUTED)
    top, base = y + 36, y + h - 24
    vmax = max((v for _, v, _ in bars if v), default=0) or 1
    slot = w / len(bars)
    width = min(slot * 0.6, 44)
    c.line([(x, base), (x + w, base)], GRID, 2)
    for i, (label, value, color) in enumerate(bars):
        cx = x + slot * (i + 0.5)
        c.text((cx, base + 6), label, 12, MUTED, "mt")
        if value is None:
            continue
        ty = base - (base - top) * value / vmax
        c.rect((cx - width / 2, ty, cx + width / 2, base), color, 3)
        c.text((cx, ty - 4), num(value, decimals, lang), 13, FG, "ms")


def workout_chart(
    title: str,
    subtitle: str,
    entries: Sequence[tuple[str, Workout]],
    hr_now: Series = (),
    hr_prev: Series = (),
    lang: str = "nl",
) -> bytes:
    """Summary card: key numbers with the difference from last time, the heart rate curve
    laid over the previous workout's, and bars for the last workouts. Entries are oldest
    first; the last one is this workout."""
    t = TEXT[lang]
    current = entries[-1][1]
    previous = entries[-2][1] if len(entries) > 1 else None
    kpis = _kpis(current, previous, lang)
    width, pad = 900, 28
    show_curve = len(hr_now) >= 2
    colors = [OTHER] * (len(entries) - 1) + [ACCENT]
    panels = [
        (t["dist_bars"], [w.distance for _, w in entries], 2),
        (t["speed"], [w.distance / w.duration * 60 if w.distance and w.duration else None for _, w in entries], 1),
        (t["hr_bars"], [w.avg_hr for _, w in entries], 0),
    ]  # fmt: skip
    panels = [p for p in panels if any(v is not None for v in p[1])]
    show_bars = len(entries) > 1 and bool(panels)

    height = 124 + (84 if kpis else 0) + (250 if show_curve else 0) + (230 if show_bars else 0)
    if not (kpis or show_curve or show_bars):
        return b""
    c = Canvas(width, height)
    c.text((pad, 24), title, 26)
    c.text((pad, 60), subtitle, 15, MUTED)
    y = 100
    if kpis:
        tile = (width - 2 * pad) / len(kpis)
        for i, (label, value, delta) in enumerate(kpis):
            x = pad + i * tile
            c.text((x, y), label, 13, MUTED)
            c.text((x, y + 20), value, 28)
            c.text((x, y + 58), delta, 13, MUTED)
        y += 84
        if previous and any(k[2] for k in kpis):
            c.text((pad, y - 4), t["note"], 12, MUTED)
        y += 22
    if show_curve:
        c.text((pad, y), t["hr_title"], 15, MUTED)
        legend = [(t["now"], ACCENT)] + ([(t["last"], OTHER)] if len(hr_prev) >= 2 else [])
        _legend(c, width - pad, y, legend)
        span = max(hr_now[-1][0], hr_prev[-1][0] if len(hr_prev) >= 2 else 0, 1)
        step = _nice_step(span, 5)
        ticks = [(m, f"{m:g} min" if m else "0") for m in _frange(0, span, step)]
        lines = [(hr_now, ACCENT, ACCENT_TINT)] + ([(hr_prev, OTHER, None)] if len(hr_prev) >= 2 else [])
        _line_chart(c, (pad, y + 26, width - pad, y + 226), lines, ticks, (0, span))
        y += 250
    if show_bars:
        c.text((pad, y), t["recent"], 15, MUTED)
        w = (width - 2 * pad - 2 * 30) / len(panels)
        for i, (name, values, decimals) in enumerate(panels):
            bars = [(label, v, col) for (label, _), v, col in zip(entries, values, colors, strict=True)]
            _bars(c, pad + i * (w + 30), y + 26, w, 190, name, bars, decimals, lang)
    return c.png()


def _frange(start: float, stop: float, step: float) -> list[float]:
    out, x = [], start
    while x <= stop + 1e-9:
        out.append(x)
        x += step
    return out


def daily_chart(
    rows: Mapping[str, Mapping[str, float | None]],
    hr_day: Mapping[str, Series] | None = None,
    lang: str = "nl",
    day: str = "",
) -> bytes:
    """Plain numbers per person and, when available, the heart rate over the day."""
    t = TEXT[lang]
    hr_day = hr_day or {}
    metrics = [m for m in ("steps", "distance", "active_kcal", "sleep", "heart_rate", "resting_heart_rate")
               if any(r.get(m) is not None for r in rows.values())]  # fmt: skip
    lines = [(s, PEOPLE[i % len(PEOPLE)], None) for i, (name, s) in enumerate(hr_day.items()) if len(s) >= 2]
    if not metrics and not lines:
        return b""
    width, pad, name_w = 900, 28, 120
    height = 90 + len(rows) * 78 + (260 if lines else 0)
    c = Canvas(width, height)
    c.text((pad, 24), f"{t['daily']} {day}".strip(), 26)
    tile = (width - 2 * pad - name_w) / max(len(metrics), 1)
    y = 84
    for i, (name, values) in enumerate(rows.items()):
        color = PEOPLE[i % len(PEOPLE)]
        c.dot(pad + 6, y + 18, 6, color)
        c.text((pad + 20, y + 8), name, 18)
        for j, metric in enumerate(metrics):
            v = values.get(metric)
            if v is None:
                text = "-"
            elif metric == "distance":
                text = f"{num(v, 1, lang)} km"
            elif metric == "sleep":
                text = f"{num(v / 60, 1, lang)} u" if lang == "nl" else f"{num(v / 60, 1, lang)} h"
            elif metric in ("heart_rate", "resting_heart_rate"):
                text = f"{num(v, 0, lang)} bpm"
            else:
                text = num(v, 0, lang)
            x = pad + name_w + j * tile
            c.text((x, y), t["km"].split(" (")[0] if metric == "distance" else t[metric], 12, MUTED)
            c.text((x, y + 18), text, 24)
        y += 78
    if lines:
        c.text((pad, y + 6), t["hr_day"], 15, MUTED)
        _legend(c, width - pad, y + 6, [(n, PEOPLE[i % len(PEOPLE)]) for i, (n, s) in enumerate(hr_day.items()) if len(s) >= 2])
        ticks = [(h, f"{h:02d}") for h in range(0, 25, 6)]
        _line_chart(c, (pad, y + 34, width - pad, y + 254), lines, ticks, (0, 24))
    return c.png()
