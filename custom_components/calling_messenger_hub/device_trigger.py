from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .event import EVENT_TYPES
from .stream import event_signal

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(EVENT_TYPES),
    }
)

def _entry_id_for_device(hass: HomeAssistant, device_id: str) -> str | None:
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None
    for entry_id in device.config_entries:
        if (DOMAIN, entry_id) not in device.identifiers:
            continue
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == DOMAIN:
            return entry_id
    return None

async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    entry_id = _entry_id_for_device(hass, device_id)
    if entry_id is None:
        return []
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: trigger_type,
        }
        for trigger_type in EVENT_TYPES
    ]

async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    entry_id = _entry_id_for_device(hass, config[CONF_DEVICE_ID])
    if entry_id is None:
        return lambda: None
    trigger_type = str(config[CONF_TYPE])
    trigger_data = trigger_info["trigger_data"]
    job = HassJob(action)

    @callback
    def _handle_stream_event(event: dict[str, Any]) -> None:
        if str(event.get("kind") or "") != trigger_type:
            return
        hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    **config,
                    "description": f"{DOMAIN} - {trigger_type}",
                    "event": dict(event),
                }
            },
        )

    return async_dispatcher_connect(
        hass,
        event_signal(entry_id),
        _handle_stream_event,
    )
