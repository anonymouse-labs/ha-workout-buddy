"""Workout Buddy: daily overview and workout summaries to a chat."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import DOMAIN
from .coordinator import WorkoutBuddy

PLATFORMS = ["button", "sensor"]

type WorkoutBuddyConfigEntry = ConfigEntry[WorkoutBuddy]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_PERSON = "person"
ATTR_SOURCE = "source"
ATTR_WORKOUT_KEY = "workout_key"


def _manager(hass: HomeAssistant) -> WorkoutBuddy:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="not_loaded"
    )


def _person(manager: WorkoutBuddy, name: str | None) -> str | None:
    if name is not None and name not in manager.persons:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_person",
            translation_placeholders={"person": name},
        )
    return name


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the domain services."""

    async def send_daily_summary(call: ServiceCall) -> None:
        manager = _manager(hass)
        if not await manager.async_send_daily(_person(manager, call.data.get(ATTR_PERSON))):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="send_failed"
            )

    async def send_workout_summary(call: ServiceCall) -> None:
        manager = _manager(hass)
        person = _person(manager, call.data[ATTR_PERSON])
        key = call.data.get(ATTR_WORKOUT_KEY)
        record = (
            manager.store.find(person, key) if key else manager.store.latest(person)
        )
        if record is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_workout"
            )
        if not await manager.async_send_workout(person, record):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="send_failed"
            )

    async def clear_history(call: ServiceCall) -> None:
        manager = _manager(hass)
        manager.store.clear(_person(manager, call.data.get(ATTR_PERSON)))
        await manager.store.async_save()
        manager._notify_entities()  # noqa: SLF001

    async def dump_source(call: ServiceCall) -> None:
        await _manager(hass).async_dump(
            call.data.get(ATTR_SOURCE), call.data.get(ATTR_ENTITY_ID)
        )

    person = {vol.Optional(ATTR_PERSON): cv.string}
    hass.services.async_register(
        DOMAIN, "send_daily_summary", send_daily_summary, vol.Schema(person)
    )
    hass.services.async_register(
        DOMAIN,
        "send_workout_summary",
        send_workout_summary,
        vol.Schema(
            {vol.Required(ATTR_PERSON): cv.string, vol.Optional(ATTR_WORKOUT_KEY): cv.string}
        ),
    )
    hass.services.async_register(DOMAIN, "clear_history", clear_history, vol.Schema(person))
    hass.services.async_register(
        DOMAIN,
        "dump_source",
        dump_source,
        vol.Schema(
            {vol.Optional(ATTR_SOURCE): cv.string, vol.Optional(ATTR_ENTITY_ID): cv.entity_id}
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: WorkoutBuddyConfigEntry) -> bool:
    manager = WorkoutBuddy(hass, entry)
    await manager.async_start()
    entry.runtime_data = manager
    entry.async_on_unload(manager.async_stop)
    entry.async_on_unload(entry.add_update_listener(_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WorkoutBuddyConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _reload(hass: HomeAssistant, entry: WorkoutBuddyConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
