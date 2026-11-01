"""Config flow: global options, persons and workout sources as subentries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)
import voluptuous as vol

from .const import (
    COMPONENTS,
    CONF_COMPARE_AVG,
    CONF_COMPONENTS,
    CONF_DAILY_MODE,
    CONF_DAILY_TIME,
    CONF_DELAY,
    CONF_DISTANCE_UNIT,
    CONF_DURATION_UNIT,
    CONF_ENERGY_UNIT,
    CONF_ENTITY_ID,
    CONF_EVENT_TYPE,
    CONF_HISTORY,
    CONF_JOINT_DEADLINE,
    CONF_JOINT_TIME,
    CONF_PERSON,
    CONF_RECIPIENT,
    CONF_SEND_SERVICE,
    CONF_SOURCE_TYPE,
    DAILY_JOINT,
    DAILY_JOINT_WAIT,
    DAILY_PER_PERSON,
    DEFAULT_COMPONENTS,
    DEFAULT_DAILY_TIME,
    DEFAULT_DELAY,
    DEFAULT_HISTORY,
    DEFAULT_JOINT_DEADLINE,
    DEFAULT_JOINT_TIME,
    DEFAULT_SEND_SERVICE,
    DOMAIN,
    FIELDS,
    SOURCE_EVENT,
    SOURCE_SENSOR,
    SOURCE_TEXT,
    SUBENTRY_PERSON,
    SUBENTRY_SOURCE,
)


def _select(options: list[str], key: str, *, multiple: bool = False) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            translation_key=key,
            mode=SelectSelectorMode.DROPDOWN,
            multiple=multiple,
        )
    )


def _suggest(d: Mapping[str, Any], key: str) -> dict[str, Any]:
    return {"suggested_value": d.get(key)} if d.get(key) is not None else {}


def _options_schema(d: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SEND_SERVICE, default=d.get(CONF_SEND_SERVICE, DEFAULT_SEND_SERVICE)): TextSelector(),
            vol.Optional(CONF_RECIPIENT, description=_suggest(d, CONF_RECIPIENT)): TextSelector(),
            vol.Required(CONF_DELAY, default=d.get(CONF_DELAY, DEFAULT_DELAY)): NumberSelector(
                NumberSelectorConfig(min=0, max=900, step=5, unit_of_measurement="s")
            ),
            vol.Required(CONF_HISTORY, default=d.get(CONF_HISTORY, DEFAULT_HISTORY)): NumberSelector(
                NumberSelectorConfig(min=5, max=200, step=1)
            ),
            vol.Required(CONF_COMPARE_AVG, default=d.get(CONF_COMPARE_AVG, False)): BooleanSelector(),
            vol.Required(CONF_DAILY_MODE, default=d.get(CONF_DAILY_MODE, DAILY_PER_PERSON)): _select(
                [DAILY_PER_PERSON, DAILY_JOINT, DAILY_JOINT_WAIT], CONF_DAILY_MODE
            ),
            vol.Required(CONF_JOINT_TIME, default=d.get(CONF_JOINT_TIME, DEFAULT_JOINT_TIME)): TimeSelector(),
            vol.Required(CONF_JOINT_DEADLINE, default=d.get(CONF_JOINT_DEADLINE, DEFAULT_JOINT_DEADLINE)): TimeSelector(),
        }
    )  # fmt: skip


class WorkoutBuddyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="Workout Buddy", data={}, options=user_input)
        return self.async_show_form(step_id="user", data_schema=_options_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return WorkoutBuddyOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_PERSON: PersonSubentryFlow, SUBENTRY_SOURCE: SourceSubentryFlow}


class WorkoutBuddyOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init", data_schema=_options_schema(self.config_entry.options)
        )


class PersonSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure a person. The name is fixed after creation (history key)."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
                unique_id=user_input[CONF_NAME].casefold(),
            )
        return self.async_show_form(step_id="user", data_schema=self._schema({}, new=True))

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(), subentry, data={**subentry.data, **user_input}
            )
        return self.async_show_form(
            step_id="reconfigure", data_schema=self._schema(subentry.data, new=False)
        )

    @staticmethod
    def _schema(d: Mapping[str, Any], *, new: bool) -> vol.Schema:
        fields: dict[Any, Any] = {}
        if new:
            fields[vol.Required(CONF_NAME)] = TextSelector()
        fields[vol.Required(CONF_COMPONENTS, default=d.get(CONF_COMPONENTS, DEFAULT_COMPONENTS))] = _select(
            list(COMPONENTS), CONF_COMPONENTS, multiple=True
        )
        for component in COMPONENTS:
            key = f"entity_{component}"
            fields[vol.Optional(key, description=_suggest(d, key))] = EntitySelector(
                EntitySelectorConfig(domain="sensor")
            )
        fields[vol.Required(CONF_DAILY_TIME, default=d.get(CONF_DAILY_TIME, DEFAULT_DAILY_TIME))] = TimeSelector()
        return vol.Schema(fields)



class SourceSubentryFlow(ConfigSubentryFlow):
    """Add a workout source: sensor with attributes, event, or text sensor."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        people = [
            s.title
            for s in self._get_entry().subentries.values()
            if s.subentry_type == SUBENTRY_PERSON
        ]
        if not people:
            return self.async_abort(reason="no_person")
        if user_input is not None:
            self._data = user_input
            return await getattr(self, f"async_step_{user_input[CONF_SOURCE_TYPE]}")()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): TextSelector(),
                    vol.Required(CONF_PERSON): SelectSelector(
                        SelectSelectorConfig(options=people, mode=SelectSelectorMode.DROPDOWN)
                    ),
                    vol.Required(CONF_SOURCE_TYPE, default=SOURCE_SENSOR): _select(
                        [SOURCE_SENSOR, SOURCE_EVENT, SOURCE_TEXT], CONF_SOURCE_TYPE
                    ),
                }
            ),
        )

    async def async_step_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._detail("sensor", user_input, EntitySelector(EntitySelectorConfig(domain="sensor")), CONF_ENTITY_ID, mapped=True)

    async def async_step_event(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._detail("event", user_input, TextSelector(), CONF_EVENT_TYPE, mapped=True)

    async def async_step_text(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._detail("text", user_input, EntitySelector(EntitySelectorConfig(domain="sensor")), CONF_ENTITY_ID, mapped=False)

    async def _detail(
        self, step_id: str, user_input: dict[str, Any] | None, selector: Any, key: str, *, mapped: bool
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {k: v for k, v in {**self._data, **user_input}.items() if v not in ("", None)}
            if mapped and not any(data.get(f"map_{f}") for f in FIELDS):
                errors["base"] = "no_mapping"
            else:
                return self.async_create_entry(title=data[CONF_NAME], data=data)
        fields: dict[Any, Any] = {vol.Required(key): selector}
        if mapped:
            for field in FIELDS:
                fields[vol.Optional(f"map_{field}")] = TextSelector()
            fields[vol.Required(CONF_DURATION_UNIT, default="min")] = _select(["s", "min", "h"], CONF_DURATION_UNIT)
            fields[vol.Required(CONF_DISTANCE_UNIT, default="km")] = _select(["m", "km", "mi"], CONF_DISTANCE_UNIT)
            fields[vol.Required(CONF_ENERGY_UNIT, default="kcal")] = _select(["kcal", "kJ"], CONF_ENERGY_UNIT)
        return self.async_show_form(
            step_id=step_id, data_schema=vol.Schema(fields), errors=errors
        )
