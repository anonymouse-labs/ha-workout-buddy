"""End to end: source -> store -> message; failures; daily overview."""

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.workout_buddy.const import DOMAIN

TEXT1 = "Outdoor Walk · 120 min · 9.32 km · 650 kcal · 100 bpm"
TEXT2 = "Outdoor Walk · 129 min · 10.52 km · 663 kcal · 97 bpm"


def _entry(**options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        options={"delay": 0, **options},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="person",
                title="Ruub",
                unique_id="ruub",
                data={
                    "components": ["steps", "distance", "heart_rate", "resting_heart_rate"],
                    "entity_steps": "sensor.ruub_steps",
                    "entity_distance": "sensor.ruub_distance",
                    "entity_heart_rate": "sensor.ruub_hr",
                    "daily_time": "20:00:00",
                },
            ),
            ConfigSubentryData(
                subentry_type="workout_source",
                title="Wandelingen",
                unique_id=None,
                data={"person": "Ruub", "source_type": "text", "entity_id": "sensor.ruub_workout"},
            ),
        ],
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    hass.config.language = "nl"
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_workout_message_comparison_and_dedupe(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "script", "whatsapp_melding")
    await _setup(hass, _entry())

    hass.states.async_set("sensor.ruub_workout", TEXT1)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["kop"] == "Workout van Ruub: Outdoor Walk"
    assert "Eerste keer" in calls[0].data["tekst"]

    hass.states.async_set("sensor.ruub_workout", TEXT2)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert "Vorige keer: +1,2 km, +9 min" in calls[1].data["tekst"]

    # same workout again (extra attribute -> new state event): no third message
    hass.states.async_set("sensor.ruub_workout", TEXT2, {"x": 1})
    await hass.async_block_till_done()
    assert len(calls) == 2

    for bad in ("unknown", "unavailable"):
        hass.states.async_set("sensor.ruub_workout", bad)
        await hass.async_block_till_done()
    assert len(calls) == 2


async def test_send_failure_is_not_marked_sent_and_retried(hass: HomeAssistant) -> None:
    async def boom(call):
        raise HomeAssistantError("down")

    hass.services.async_register("script", "whatsapp_melding", boom)
    entry = _entry()
    await _setup(hass, entry)
    manager = entry.runtime_data

    hass.states.async_set("sensor.ruub_workout", TEXT1)
    await hass.async_block_till_done()
    record = manager.store.latest("Ruub")
    assert record["sent"] is False and record["attempts"] == 1

    hass.services.async_remove("script", "whatsapp_melding")
    calls = async_mock_service(hass, "script", "whatsapp_melding")
    await manager._retry_unsent()
    assert record["sent"] is True and len(calls) == 1

    await manager._retry_unsent()  # sent workouts are not retried
    assert len(calls) == 1


async def test_gives_up_after_three_attempts(hass: HomeAssistant) -> None:
    entry = _entry()
    await _setup(hass, entry)
    manager = entry.runtime_data
    hass.states.async_set("sensor.ruub_workout", TEXT1)  # no service registered
    await hass.async_block_till_done()
    for _ in range(5):
        await manager._retry_unsent()
    assert manager.store.latest("Ruub")["attempts"] == 3


async def test_daily_overview_shows_dash_for_missing(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "script", "whatsapp_melding")
    await _setup(hass, _entry())
    hass.states.async_set("sensor.ruub_steps", "8420")
    hass.states.async_set("sensor.ruub_distance", "6100", {"unit_of_measurement": "m"})
    hass.states.async_set("sensor.ruub_hr", "unavailable")

    await hass.services.async_call(DOMAIN, "send_daily_summary", {"person": "Ruub"}, blocking=True)
    assert calls[0].data["kop"] == "Dagoverzicht"
    assert calls[0].data["tekst"] == "Ruub: 8.420 stappen, 6,1 km, hartslag -, rust -"


async def test_missing_recipient_logs_error(hass: HomeAssistant, caplog) -> None:
    await _setup(hass, _entry(send_service="whatsapp_notifier.send_message"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "send_daily_summary", {}, blocking=True)
    assert "No recipient (chat ID) configured" in caplog.text


async def test_whatsapp_notifier_group(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "whatsapp_notifier", "send_message")
    await _setup(hass, _entry(send_service="whatsapp_notifier.send_message", recipient="123@g.us"))
    await hass.services.async_call(DOMAIN, "send_daily_summary", {}, blocking=True)
    assert calls[0].data["chat_id"] == "123@g.us"
    assert calls[0].data["message"].startswith("📊 Dagoverzicht")


async def test_clear_history_and_dump(hass: HomeAssistant) -> None:
    async_mock_service(hass, "script", "whatsapp_melding")
    notes = async_mock_service(hass, "persistent_notification", "create")
    entry = _entry()
    await _setup(hass, entry)
    hass.states.async_set("sensor.ruub_workout", TEXT1, {"a": 1})
    await hass.async_block_till_done()
    assert entry.runtime_data.store.latest("Ruub")

    await hass.services.async_call(DOMAIN, "dump_source", {"source": "Wandelingen"}, blocking=True)
    assert "Outdoor Walk" in notes[0].data["message"] and "'a': 1" in notes[0].data["message"]

    await hass.services.async_call(DOMAIN, "clear_history", {"person": "Ruub"}, blocking=True)
    assert entry.runtime_data.store.latest("Ruub") is None
