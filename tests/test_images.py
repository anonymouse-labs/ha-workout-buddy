"""Chart images go along with the messages when enabled."""

import os

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
