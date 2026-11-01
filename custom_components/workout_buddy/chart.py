"""PNG bar charts: the last workouts of one type, or people side by side."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import io
import math

from PIL import Image, ImageDraw, ImageFont

from .messages import num
from .parser import Workout

BG, FG, MUTED, GRID = (255, 255, 255), (33, 37, 41), (108, 117, 125), (222, 226, 230)
ACCENT, OTHER = (18, 150, 126), (173, 181, 189)
PEOPLE = [(18, 150, 126), (245, 159, 0), (73, 80, 214), (214, 51, 108)]

PANEL_W, PANEL_H, PAD, HEAD = 270, 230, 20, 56

TITLES = {
    "nl": {
        "distance": "Afstand (km)", "speed": "Snelheid (km/u)", "avg_hr": "Hartslag (bpm)",
        "steps": "Stappen", "heart_rate": "Hartslag (bpm)", "resting_heart_rate": "Rusthartslag (bpm)",
        "active_kcal": "Actieve kcal", "sleep": "Slaap (u)", "daily": "Dagoverzicht",
    },
    "en": {
        "distance": "Distance (km)", "speed": "Speed (km/h)", "avg_hr": "Heart rate (bpm)",
        "steps": "Steps", "heart_rate": "Heart rate (bpm)", "resting_heart_rate": "Resting heart rate (bpm)",
        "active_kcal": "Active kcal", "sleep": "Sleep (h)", "daily": "Daily overview",
    },
}  # fmt: skip

Bar = tuple[str, float | None, tuple[int, int, int]]
Panel = tuple[str, list[Bar], int]  # title, bars, decimals


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _draw_panel(d: ImageDraw.ImageDraw, x: int, y: int, panel: Panel, lang: str) -> None:
    title, bars, decimals = panel
    d.text((x, y), title, font=_font(16), fill=MUTED)
    top, base = y + 44, y + PANEL_H - 28
    vmax = max((v for _, v, _ in bars if v), default=0) or 1
    slot = (PANEL_W - PAD) / len(bars)
    width = min(slot * 0.62, 56)
    d.line((x, base, x + PANEL_W - PAD, base), fill=GRID, width=2)
    for i, (label, value, color) in enumerate(bars):
        cx = x + slot * (i + 0.5)
        d.text((cx, base + 6), label, anchor="mt", font=_font(13), fill=MUTED)
        if value is None:
            continue
        top_y = base - (base - top) * value / vmax
        d.rounded_rectangle((cx - width / 2, top_y, cx + width / 2, base), 4, fill=color)
        d.text((cx, top_y - 4), num(value, decimals, lang), anchor="ms", font=_font(14), fill=FG)


def _render(title: str, panels: Sequence[Panel], lang: str) -> bytes:
    cols = min(len(panels), 3)
    rows = math.ceil(len(panels) / cols)
    img = Image.new("RGB", (PAD + cols * PANEL_W, HEAD + rows * PANEL_H + PAD // 2), BG)
    d = ImageDraw.Draw(img)
    d.text((PAD, PAD - 2), title, font=_font(22), fill=FG)
    for i, panel in enumerate(panels):
        _draw_panel(d, PAD + (i % cols) * PANEL_W, HEAD + (i // cols) * PANEL_H, panel, lang)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def workout_chart(
    title: str, entries: Sequence[tuple[str, Workout]], lang: str = "nl"
) -> bytes:
    """Distance, speed and heart rate of the given workouts; the last bar is the new one."""
    t = TITLES[lang]
    colors = [OTHER] * (len(entries) - 1) + [ACCENT]

    def bars(values: list[float | None]) -> list[Bar]:
        return [(label, v, c) for (label, _), v, c in zip(entries, values, colors, strict=True)]

    series = {
        "distance": ([w.distance for _, w in entries], 2),
        "speed": ([w.distance / w.duration * 60 if w.distance and w.duration else None for _, w in entries], 1),
        "avg_hr": ([w.avg_hr for _, w in entries], 0),
    }  # fmt: skip
    panels = [(t[k], bars(v), dec) for k, (v, dec) in series.items() if any(x is not None for x in v)]
    return _render(title, panels, lang) if panels else b""


def daily_chart(
    rows: Mapping[str, Mapping[str, float | None]], lang: str = "nl", day: str = ""
) -> bytes:
    """One panel per metric, one bar per person."""
    t = TITLES[lang]
    decimals = {"distance": 1, "sleep": 1}
    panels: list[Panel] = []
    for metric in ("steps", "distance", "heart_rate", "resting_heart_rate", "active_kcal", "sleep"):
        values = [vals.get(metric) for vals in rows.values()]
        if all(v is None for v in values):
            continue
        if metric == "sleep":
            values = [v / 60 if v is not None else None for v in values]
        bars = [(name, v, PEOPLE[i % len(PEOPLE)]) for i, (name, v) in enumerate(zip(rows, values, strict=True))]
        panels.append((t[metric], bars, decimals.get(metric, 0)))
    return _render(f"{t['daily']} {day}".strip(), panels, lang) if panels else b""
