from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TelegramVoipCoordinator
from .entity import TelegramVoipEntity

EVENT_TYPES = ["call", "ring", "alert"]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TelegramVoipCoordinator = entry.runtime_data.coordinator
    async_add_entities([ActivityEvent(coordinator, entry)])

def _item_key(item: dict[str, Any], kind: str) -> str:
    return str(
        item.get("id")
        or item.get("alert_id")
        or item.get("ring_id")
        or f"{kind}:{item.get('created_at')}:{item.get('peer_id') or item.get('to') or ''}"
    )

def _item_summary(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "account_id",
        "service",
        "kind",
        "status",
        "name",
        "peer_id",
        "peer_name",
        "to",
        "message",
        "severity",
        "created_at",
    )
    return {
        key: item[key]
        for key in keys
        if item.get(key) not in (None, "")
    }

class ActivityEvent(TelegramVoipEntity, EventEntity):
    _attr_translation_key = "activity"
    _attr_event_types = EVENT_TYPES

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_activity"
        self._seen: dict[str, set[str]] = {
            "call": set(),
            "ring": set(),
            "alert": set(),
        }
        self._remember(self.coordinator.data or {})

    def _remember(self, data: dict[str, Any]) -> None:
        for kind, key in (
            ("call", "calls"),
            ("ring", "rings"),
            ("alert", "alerts"),
        ):
            for item in data.get(key) or []:
                self._seen[kind].add(_item_key(item, kind))

    @callback
    def _handle_coordinator_update(self) -> None:
        data = dict(self.coordinator.data or {})
        new_items: dict[str, list[dict[str, Any]]] = {}
        for kind, key in (
            ("call", "calls"),
            ("ring", "rings"),
            ("alert", "alerts"),
        ):
            fresh = []
            for item in data.get(key) or []:
                item_key = _item_key(item, kind)
                if item_key not in self._seen[kind]:
                    fresh.append(item)
                    self._seen[kind].add(item_key)
            if fresh:
                new_items[kind] = fresh
        if not new_items:
            self.async_write_ha_state()
            return
        for kind, items in new_items.items():
            self._trigger_event(
                kind,
                {
                    "new_count": len(items),
                    "item": _item_summary(items[0]),
                },
            )
            self.async_write_ha_state()
