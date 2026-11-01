"""Chart images go along with the messages when enabled."""

import os
from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.workout_buddy.coordinator import WorkoutBuddy

from .test_extra import TEXT1, _entry, _setup

TEXT2 = "Outdoor Walk · 129 min · 10.52 km · 663 kcal · 97 bpm"


async def test_workout_image_for_whatsapp_notifier(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "whatsapp_notifier", "send_message")
    entry = _entry(
        send_service="whatsapp_notifier.send_message", recipient="1@g.us", send_images=True
    )
    await _setup(hass, entry)
    for text in (TEXT1, TEXT2):
        hass.states.async_set("sensor.w", text)
        await hass.async_block_till_done()
    image = calls[1].data["image"]
    assert image.endswith("workout_ruub.png") and os.path.getsize(image) > 1000
    assert "www" in image and calls[1].data["chat_id"] == "1@g.us"


async def test_script_gets_image_field(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "script", "whatsapp_melding")
    await _setup(hass, _entry(send_images=True))
    for text in (TEXT1, TEXT2):
        hass.states.async_set("sensor.w", text)
        await hass.async_block_till_done()
    assert calls[1].data["afbeelding"].endswith("workout_ruub.png")


async def test_no_image_by_default(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "script", "whatsapp_melding")
    await _setup(hass, _entry())
    hass.states.async_set("sensor.w", TEXT1)
    await hass.async_block_till_done()
    assert "afbeelding" not in calls[0].data


async def test_falls_back_to_text_when_image_is_rejected(hass: HomeAssistant) -> None:
    seen = []

    async def strict(call) -> None:  # like a notifier that does not know `image`
        seen.append(dict(call.data))
        if "image" in call.data:
            raise HomeAssistantError("extra keys not allowed")

    hass.services.async_register("whatsapp_notifier", "send_message", strict)
    entry = _entry(
        send_service="whatsapp_notifier.send_message", recipient="1@g.us", send_images=True
    )
    await _setup(hass, entry)
    hass.states.async_set("sensor.w", TEXT1)
    await hass.async_block_till_done()
    assert len(seen) == 2 and "image" not in seen[1]
    assert entry.runtime_data.store.latest("Ruub")["sent"] is True


async def test_heart_rate_curve_is_stored_and_compared(hass: HomeAssistant) -> None:
    async def fake_history(self, entity_id, start, end):
        return [(start + timedelta(minutes=m), 90.0 + m) for m in range(0, 61, 5)]

    calls = async_mock_service(hass, "whatsapp_notifier", "send_message")
    entry = _entry(
        send_service="whatsapp_notifier.send_message", recipient="1@g.us", send_images=True
    )
    with patch.object(WorkoutBuddy, "_history", fake_history):
        await _setup(hass, entry)
        for text in (TEXT1, TEXT2):
            hass.states.async_set("sensor.w", text)
            await hass.async_block_till_done()
    store = entry.runtime_data.store
    latest = store.latest("Ruub")
    assert 2 <= len(latest["hr"]) <= 60 and latest["hr"][0][0] >= 0
    assert store.previous("Ruub", latest)[-1]["hr"]  # the earlier workout kept its curve
    assert os.path.getsize(calls[1].data["image"]) > 5000


async def test_daily_image_with_day_curve(hass: HomeAssistant) -> None:
    async def fake_history(self, entity_id, start, end):
        return [(start + timedelta(hours=h), 60.0 + h) for h in range(0, 10)]

    calls = async_mock_service(hass, "whatsapp_notifier", "send_message")
    entry = _entry(
        send_service="whatsapp_notifier.send_message", recipient="1@g.us", send_images=True
    )
    with patch.object(WorkoutBuddy, "_history", fake_history):
        await _setup(hass, entry)
        await hass.services.async_call("workout_buddy", "send_daily_summary", {}, blocking=True)
    assert os.path.getsize(calls[0].data["image"]) > 5000


async def test_chart_only_without_text(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "whatsapp_notifier", "send_message")
    entry = _entry(
        send_service="whatsapp_notifier.send_message",
        recipient="1@g.us",
        send_images=True,
        send_text=False,
    )
    await _setup(hass, entry)
    hass.states.async_set("sensor.ruub_steps", "100")
    await hass.services.async_call("workout_buddy", "send_daily_summary", {}, blocking=True)
    assert calls[0].data["message"] == "" and calls[0].data["image"].endswith("daily.png")


async def test_text_is_kept_when_the_channel_cannot_send_images(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "notify", "mobile")
    entry = _entry(send_service="notify.mobile", send_images=True, send_text=False)
    await _setup(hass, entry)
    await hass.services.async_call("workout_buddy", "send_daily_summary", {}, blocking=True)
    assert "Dagoverzicht" in calls[0].data["message"] and "image" not in calls[0].data


async def test_daily_heart_rate_shows_lowest_and_highest(hass: HomeAssistant) -> None:
    async def fake_history(self, entity_id, start, end):
        return [(start + timedelta(hours=h), 60.0 + h) for h in (1, 5, 9)]

    calls = async_mock_service(hass, "script", "whatsapp_melding")
    entry = _entry(components=("steps", "heart_rate"))
    with patch.object(WorkoutBuddy, "_history", fake_history):
        await _setup(hass, entry)
        hass.states.async_set("sensor.ruub_hr", "111")  # latest reading must not be shown
        await hass.services.async_call("workout_buddy", "send_daily_summary", {}, blocking=True)
    assert calls[0].data["tekst"] == "Ruub: stappen -, hartslag 61-69 bpm"
