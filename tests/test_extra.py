"""Event and attribute sources, orphan sources, in-flight guard, joint modes."""

import asyncio
from datetime import time, timedelta
from unittest.mock import patch

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.workout_buddy.const import DOMAIN

TEXT1 = "Outdoor Walk · 120 min · 9.32 km · 650 kcal · 100 bpm"
COORD = "custom_components.workout_buddy.coordinator"


def _entry(source: dict | None = None, components: tuple = ("steps",), **options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        options={"delay": 0, **options},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="person",
                title="Ruub",
                unique_id="ruub",
                data={
                    "components": list(components),
                    "entity_steps": "sensor.ruub_steps",
                    "entity_heart_rate": "sensor.ruub_hr",
                    "daily_time": "20:00:00",
                },
            ),
            ConfigSubentryData(
                subentry_type="workout_source",
                title="Bron",
                unique_id=None,
                data=source
                or {"person": "Ruub", "source_type": "text", "entity_id": "sensor.w"},
            ),
        ],
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    hass.config.language = "nl"
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_event_source(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "script", "whatsapp_melding")
    source = {
        "person": "Ruub",
        "source_type": "event",
        "event_type": "my_workout",
        "map_type": "kind",
        "map_distance": "dist",
        "map_duration": "dur",
        "duration_unit": "s",
    }
    await _setup(hass, _entry(source))
    hass.bus.async_fire("my_workout", {"kind": "Run", "dist": 5, "dur": 1500})
    await hass.async_block_till_done()
    assert calls[0].data["kop"] == "Workout van Ruub: Run"
    assert calls[0].data["tekst"].startswith("25 min, 5,00 km")


async def test_sensor_attribute_source(hass: HomeAssistant, caplog) -> None:
    calls = async_mock_service(hass, "script", "whatsapp_melding")
    source = {
        "person": "Ruub",
        "source_type": "sensor",
        "entity_id": "sensor.w",
        "map_type": "type",
        "map_distance": "distance",
    }
    await _setup(hass, _entry(source))
    hass.states.async_set("sensor.w", "done", {"type": "Cycling", "distance": "20 km"})
    await hass.async_block_till_done()
    assert calls[0].data["tekst"].startswith("20,00 km")

    hass.states.async_set("sensor.w", "again", {"other": 1})  # nothing mapped is present
    await hass.async_block_till_done()
    assert "gave no usable workout" in caplog.text


async def test_source_of_removed_person_is_ignored(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "script", "whatsapp_melding")
    entry = _entry({"person": "Nobody", "source_type": "text", "entity_id": "sensor.w"})
    await _setup(hass, entry)
    assert entry.runtime_data.sources == []
    hass.states.async_set("sensor.w", TEXT1)
    await hass.async_block_till_done()
    assert calls == []


async def test_no_double_send_while_in_flight(hass: HomeAssistant) -> None:
    entry = _entry()
    await _setup(hass, entry)
    manager = entry.runtime_data
    hass.states.async_set("sensor.w", TEXT1)  # no service yet: fails once
    await hass.async_block_till_done()
    record = manager.store.latest("Ruub")
    assert record["attempts"] == 1

    gate = asyncio.Event()

    async def slow(call) -> None:
        await gate.wait()

    hass.services.async_register("script", "whatsapp_melding", slow)
    first = hass.async_create_task(manager.async_send_workout("Ruub", record))
    await asyncio.sleep(0)
    assert await manager.async_send_workout("Ruub", record) is False  # already sending
    gate.set()
    assert await first is True


async def test_joint_wait_sends_when_synced_or_at_deadline(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "script", "whatsapp_melding")
    entry = _entry(daily_mode="joint_wait", joint_time="20:00:00", joint_deadline="22:00:00")
    await _setup(hass, entry)
    manager = entry.runtime_data

    with (
        patch.object(manager, "_synced_today", return_value=False),
        patch(f"{COORD}.dt_util.now") as now,
    ):
        now.return_value.time.return_value = time(20, 0)
        await manager._joint_start(None)
        assert calls == []  # waiting for sync
        now.return_value.time.return_value = time(22, 5)
        await manager._joint_tick()
        assert len(calls) == 1  # deadline passed
        await manager._joint_tick()
        assert len(calls) == 1  # sent once only

    manager._joint_pending = True
    with patch.object(manager, "_synced_today", return_value=True):
        await manager._joint_tick()
    assert len(calls) == 2


async def test_synced_today_compares_with_midnight(hass: HomeAssistant) -> None:
    entry = _entry()
    await _setup(hass, entry)
    manager = entry.runtime_data
    hass.states.async_set("sensor.ruub_steps", "1")
    assert manager._synced_today() is True
    tomorrow = dt_util.start_of_local_day() + timedelta(days=1)
    with patch(f"{COORD}.dt_util.start_of_local_day", return_value=tomorrow):
        assert manager._synced_today() is False
