from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .accounts import AccountEntityRegistry, account_by_id, account_device_info
from .coordinator import TelegramVoipCoordinator
from .entity import TelegramVoipEntity, TelegramVoipStreamEntity


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
            EventStreamLastEventSensor(coordinator, entry),
            EventStreamReconnectsSensor(coordinator, entry),
        ]
    )

    def account_entities(account: dict[str, Any]) -> list[tuple[str, SensorEntity]]:
        if account.get("service") != "sim":
            return []
        account_id = str(account.get("id"))
        return [
            (f"{account_id}:signal", AccountSignalSensor(coordinator, entry, account)),
            (f"{account_id}:carrier", AccountCarrierSensor(coordinator, entry, account)),
            (f"{account_id}:balance", AccountBalanceSensor(coordinator, entry, account)),
            (f"{account_id}:expiry", AccountExpirySensor(coordinator, entry, account)),
        ]

    registry = AccountEntityRegistry(coordinator, async_add_entities, account_entities)
    entry.async_on_unload(registry.async_stop)


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


class AccountSensor(TelegramVoipSensor):
    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
        account: dict[str, Any],
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            device_info=account_device_info(coordinator, entry, account),
        )
        self._account_id = str(account.get("id"))

    @property
    def _account(self) -> dict[str, Any]:
        return account_by_id(self.coordinator.data, self._account_id)


class AccountSignalSensor(AccountSensor):
    _attr_translation_key = "account_signal"
    _attr_icon = "mdi:signal"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
        account: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, entry, account)
        self._attr_unique_id = f"{entry.entry_id}_{self._account_id}_signal"

    @property
    def native_value(self) -> int | None:
        value = self._account.get("signal_percent")
        if value is None:
            return None
        try:
            return max(0, min(100, int(value)))
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        account = self._account
        return {
            "signal_dbm": account.get("signal_dbm"),
            "signal_level": account.get("signal_level"),
            "carrier": account.get("carrier"),
            "network": account.get("network"),
        }


class AccountCarrierSensor(AccountSensor):
    _attr_translation_key = "account_carrier"
    _attr_icon = "mdi:sim"

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
        account: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, entry, account)
        self._attr_unique_id = f"{entry.entry_id}_{self._account_id}_carrier"

    @property
    def native_value(self) -> str | None:
        return str(self._account.get("carrier") or "")[:255] or None


class AccountBalanceSensor(AccountSensor):
    _attr_translation_key = "account_balance"
    _attr_icon = "mdi:cash"

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
        account: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, entry, account)
        self._attr_unique_id = f"{entry.entry_id}_{self._account_id}_balance"

    @property
    def native_value(self) -> str | None:
        return str(self._account.get("balance") or "")[:255] or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        account = self._account
        return {
            "balance_updated_at": account.get("balance_updated_at"),
            "expiry": account.get("expiry"),
        }


class AccountExpirySensor(AccountSensor):
    _attr_translation_key = "account_expiry"
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
        account: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, entry, account)
        self._attr_unique_id = f"{entry.entry_id}_{self._account_id}_expiry"

    @property
    def native_value(self) -> str | None:
        return str(self._account.get("expiry") or "")[:255] or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "balance_updated_at": self._account.get("balance_updated_at"),
        }


def _event_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), UTC)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    parsed = dt_util.parse_datetime(text)
    if parsed is None:
        try:
            return datetime.fromtimestamp(float(text), UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


class EventStreamLastEventSensor(TelegramVoipStreamEntity, SensorEntity):
    _attr_translation_key = "event_stream_last_event"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:message-flash"

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_event_stream_last_event"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> datetime | None:
        return _event_time(self._stream.snapshot().get("last_event_at"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self._stream.snapshot()
        return {
            "event_id": status.get("last_event_id"),
            "event_kind": status.get("last_event_kind"),
            "events_received": status.get("events_received"),
            "reconnects": status.get("reconnects"),
        }


class EventStreamReconnectsSensor(TelegramVoipStreamEntity, SensorEntity):
    _attr_translation_key = "event_stream_reconnects"
    _attr_icon = "mdi:reload-alert"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_event_stream_reconnects"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> int:
        return int(self._stream.snapshot().get("reconnects", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self._stream.snapshot()
        return {
            "connected": status.get("connected"),
            "connected_since": status.get("connected_since"),
            "last_error": status.get("last_error"),
        }
