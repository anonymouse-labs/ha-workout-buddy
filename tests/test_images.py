"""Chart images go along with the messages when enabled."""

import os

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_mock_service

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
