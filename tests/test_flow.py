"""Config flow: options, person and workout source subentries."""

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.workout_buddy.const import DOMAIN

OPTIONS = {
    "send_service": "script.whatsapp_melding",
    "delay": 60,
    "history_size": 20,
    "compare_average": False,
    "daily_mode": "per_person",
    "joint_time": "20:00:00",
    "joint_deadline": "22:30:00",
}


async def _sub(hass: HomeAssistant, entry_id: str, kind: str):
    return await hass.config_entries.subentries.async_init(
        (entry_id, kind), context={"source": "user"}
    )


async def test_flow_person_and_sources(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], OPTIONS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry_id = result["result"].entry_id
    options = result["result"].options
    assert options["send_text"] is True and options["chart_parts"] == ["numbers", "curves", "bars"]
    assert options["daily_curves"] == ["heart_rate"]
    configure = hass.config_entries.subentries.async_configure

    flow = await _sub(hass, entry_id, "workout_source")  # a source needs a person first
    assert flow["type"] is FlowResultType.ABORT and flow["reason"] == "no_person"

    flow = await _sub(hass, entry_id, "person")
    flow = await configure(
        flow["flow_id"], {"name": "Ruub", "components": ["steps"], "daily_time": "20:00:00"}
    )
    assert flow["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    flow = await _sub(hass, entry_id, "workout_source")
    flow = await configure(
        flow["flow_id"], {"name": "Bron", "person": "Ruub", "source_type": "sensor"}
    )
    assert flow["step_id"] == "sensor"
    flow = await configure(flow["flow_id"], {"entity_id": "sensor.w"})
    assert flow["type"] is FlowResultType.FORM and flow["errors"] == {"base": "no_mapping"}
    flow = await configure(flow["flow_id"], {"entity_id": "sensor.w", "map_distance": "dist"})
    assert flow["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    flow = await _sub(hass, entry_id, "workout_source")  # text source: only the sensor
    flow = await configure(
        flow["flow_id"], {"name": "Tekst", "person": "Ruub", "source_type": "text"}
    )
    flow = await configure(flow["flow_id"], {"entity_id": "sensor.t"})
    assert flow["type"] is FlowResultType.CREATE_ENTRY


async def test_single_instance(hass: HomeAssistant) -> None:
    first = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    await hass.config_entries.flow.async_configure(first["flow_id"], OPTIONS)
    second = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert second["type"] is FlowResultType.ABORT
