from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .accounts import AccountEntityRegistry, account_by_id, account_device_info
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
            ApiOnlineBinarySensor(coordinator, entry),
            LicenseValidBinarySensor(coordinator, entry),
            MqttConnectedBinarySensor(coordinator, entry),
            SimProblemBinarySensor(coordinator, entry),
            UpdateAvailableBinarySensor(coordinator, entry),
        ]
    )
    registry = AccountEntityRegistry(
        coordinator,
        async_add_entities,
        lambda account: [
            (
                f"{account.get('id')}:online",
                AccountOnlineBinarySensor(coordinator, entry, account),
            )
        ],
    )
    entry.async_on_unload(registry.async_stop)

class TelegramVoipBinarySensor(TelegramVoipEntity, BinarySensorEntity):
    pass

class ApiOnlineBinarySensor(TelegramVoipBinarySensor):
    _attr_translation_key = "api_online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_api_online"

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success

class LicenseValidBinarySensor(TelegramVoipBinarySensor):
    _attr_translation_key = "license_valid"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_license_valid"

    @property
    def _license(self) -> dict[str, Any]:
        return dict(self.coordinator.data.get("license") or {})

    @property
    def is_on(self) -> bool:
        return bool(self._license.get("valid"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        license_data = self._license
        return {
            "configured": license_data.get("configured"),
            "reason": license_data.get("reason"),
            "reason_label": license_data.get("reason_label"),
            "plan_name": license_data.get("plan_name"),
            "expires_at": license_data.get("expires_at"),
            "days_remaining": license_data.get("days_remaining"),
            "key_masked": license_data.get("key_masked"),
        }

class MqttConnectedBinarySensor(TelegramVoipBinarySensor):
    _attr_translation_key = "mqtt_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_mqtt_connected"

    @property
    def _mqtt(self) -> dict[str, Any]:
        return dict(self.coordinator.data.get("mqtt") or {})

    @property
    def available(self) -> bool:
        return super().available and bool(self._mqtt)

    @property
    def is_on(self) -> bool:
        mqtt = self._mqtt
        return bool(mqtt.get("enabled") and mqtt.get("connected"))

class SimProblemBinarySensor(TelegramVoipBinarySensor):
    _attr_translation_key = "sim_problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_sim_problem"

    @property
    def _health(self) -> dict[str, Any]:
        return dict(self.coordinator.data.get("sim_health") or {})

    @property
    def available(self) -> bool:
        return super().available and bool(self._health.get("configured"))

    @property
    def is_on(self) -> bool:
        return not bool(self._health.get("healthy", True))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        health = self._health
        return {
            "status": health.get("status"),
            "count": health.get("count"),
            "online": health.get("online"),
            "issues": health.get("issues", []),
            "checked_at": health.get("checked_at"),
        }

class UpdateAvailableBinarySensor(TelegramVoipBinarySensor):
    _attr_translation_key = "update_available"
    _attr_device_class = BinarySensorDeviceClass.UPDATE

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_update_available"

    @property
    def _update(self) -> dict[str, Any]:
        return dict(self.coordinator.data.get("update") or {})

    @property
    def is_on(self) -> bool:
        return bool(self._update.get("update_available"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        update = self._update
        return {
            "current_version": update.get("current_version"),
            "latest_version": update.get("latest_version"),
            "checked_at": update.get("checked_at"),
            "url": update.get("url"),
            "error": update.get("error"),
        }


class AccountOnlineBinarySensor(TelegramVoipBinarySensor):
    _attr_translation_key = "account_online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

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
        self._attr_unique_id = f"{entry.entry_id}_{self._account_id}_online"

    @property
    def _account(self) -> dict[str, Any]:
        return account_by_id(self.coordinator.data, self._account_id)

    @property
    def is_on(self) -> bool:
        return self._account.get("state") == "online"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        account = self._account
        return {
            "account_id": self._account_id,
            "service": account.get("service"),
            "phone": account.get("phone"),
            "state": account.get("state"),
            "driver": account.get("driver"),
            "channel": account.get("channel"),
            "network": account.get("network"),
            "last_error": account.get("last_error"),
            "last_seen_at": account.get("last_seen_at"),
            "last_connected_at": account.get("last_connected_at"),
            "latency_ms": account.get("latency_ms"),
            "reconnect_attempts": account.get("reconnect_attempts"),
            "next_retry_at": account.get("next_retry_at"),
            "event_connected": account.get("event_connected"),
            "event_error": account.get("event_error"),
        }
