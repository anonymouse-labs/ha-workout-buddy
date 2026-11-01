"""Button to send the daily overview now."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WorkoutBuddyConfigEntry
from .const import DOMAIN
from .entity import PersonEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WorkoutBuddyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    for person in manager.persons.values():
        async_add_entities(
            [SendDailyButton(manager, person, "send_daily")],
            config_subentry_id=person.subentry_id,
        )


class SendDailyButton(PersonEntity, ButtonEntity):
    async def async_press(self) -> None:
        if not await self.manager.async_send_daily(self.person.name):
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="send_failed")
