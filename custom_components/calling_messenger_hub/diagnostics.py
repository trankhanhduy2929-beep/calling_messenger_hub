from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

TO_REDACT = {
    "token",
    "password",
    "api_token",
    "api_hash",
    "license_key",
    "authorization",
}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    runtime = getattr(entry, "runtime_data", None)
    coordinator = getattr(runtime, "coordinator", None)
    api = getattr(runtime, "api", None)
    return async_redact_data(
        {
            "entry": {
                "data": dict(entry.data),
                "options": dict(entry.options),
                "version": entry.version,
            },
            "base_url": getattr(api, "base_url", None),
            "last_update_success": getattr(coordinator, "last_update_success", None),
            "status": getattr(coordinator, "data", None) or {},
        },
        TO_REDACT,
    )
