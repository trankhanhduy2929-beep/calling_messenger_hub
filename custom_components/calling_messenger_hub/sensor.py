from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TelegramVoipCoordinator
from .entity import TelegramVoipEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TelegramVoipCoordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            AccountsOnlineSensor(coordinator, entry),
            ActiveCallsSensor(coordinator, entry),
            AlertsActiveSensor(coordinator, entry),
            AlertsUnacknowledgedSensor(coordinator, entry),
        ]
    )


class TelegramVoipSensor(TelegramVoipEntity, SensorEntity):
    pass


class AccountsOnlineSensor(TelegramVoipSensor):
    _attr_translation_key = "accounts_online"
    _attr_icon = "mdi:account-multiple-check"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_accounts_online"

    @property
    def native_value(self) -> int:
        return int(self.coordinator.data.get("accounts_online", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        accounts = self.coordinator.data.get("accounts", [])
        return {
            "accounts": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "phone": item.get("phone"),
                    "state": item.get("state"),
                    "me": item.get("me"),
                    "last_error": item.get("last_error"),
                }
                for item in accounts
            ],
            "version": self.coordinator.data.get("version"),
            "started_at": self.coordinator.data.get("started_at"),
        }


class ActiveCallsSensor(TelegramVoipSensor):
    _attr_translation_key = "active_calls"
    _attr_icon = "mdi:phone-in-talk"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_active_calls"

    @property
    def native_value(self) -> int:
        return int(self.coordinator.data.get("active_calls", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "calls": self.coordinator.data.get("calls", []),
            "rings": self.coordinator.data.get("rings", []),
            "stats": self.coordinator.data.get("stats", {}),
            "tts": self.coordinator.data.get("tts", {}),
        }

class AlertsActiveSensor(TelegramVoipSensor):
    _attr_translation_key = "alerts_active"
    _attr_icon = "mdi:alert-circle"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_alerts_active"

    @property
    def native_value(self) -> int:
        return int(self.coordinator.data.get("alerts_active", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"alerts": self.coordinator.data.get("alerts", [])}


class AlertsUnacknowledgedSensor(TelegramVoipSensor):
    _attr_translation_key = "alerts_unacknowledged"
    _attr_icon = "mdi:alert-decagram"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_alerts_unacknowledged"

    @property
    def native_value(self) -> int:
        return int(self.coordinator.data.get("alerts_unacknowledged", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        alerts = [
            item
            for item in self.coordinator.data.get("alerts", [])
            if not item.get("acknowledged_at")
        ]
        return {"alerts": alerts}
