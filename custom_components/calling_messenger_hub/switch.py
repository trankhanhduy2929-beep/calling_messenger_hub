from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import TelegramVoipApiError
from .coordinator import TelegramVoipCoordinator
from .entity import TelegramVoipEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TelegramVoipCoordinator = entry.runtime_data.coordinator
    async_add_entities([MqttBridgeSwitch(coordinator, entry)])

class MqttBridgeSwitch(TelegramVoipEntity, SwitchEntity):
    _attr_translation_key = "mqtt_bridge"
    _attr_icon = "mdi:lan-connect"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_mqtt_bridge"

    @property
    def _mqtt(self) -> dict[str, Any]:
        return dict(self.coordinator.data.get("mqtt") or {})

    @property
    def available(self) -> bool:
        return super().available and bool(self._mqtt)

    @property
    def is_on(self) -> bool:
        return bool(self._mqtt.get("enabled"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mqtt = self._mqtt
        return {
            "connected": mqtt.get("connected"),
            "host": mqtt.get("host"),
            "port": mqtt.get("port"),
            "tls": mqtt.get("tls"),
            "topic_prefix": mqtt.get("topic_prefix"),
            "discovery_prefix": mqtt.get("discovery_prefix"),
            "error": mqtt.get("error"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        try:
            config = await self.coordinator.api.async_config()
        except TelegramVoipApiError as err:
            raise HomeAssistantError(str(err)) from err
        mqtt = dict(config.get("mqtt") or {})
        if enabled and not mqtt.get("host"):
            raise HomeAssistantError(
                "Configure the MQTT host in the Calling Messenger Hub settings first"
            )
        try:
            result = await self.coordinator.api.async_update_mqtt_settings(
                enabled=enabled,
                host=str(mqtt.get("host") or ""),
                port=int(mqtt.get("port") or 1883),
                username=str(mqtt.get("username") or ""),
                tls=bool(mqtt.get("tls")),
                topic_prefix=str(mqtt.get("topic_prefix") or "calling_messenger_hub"),
                discovery_prefix=str(mqtt.get("discovery_prefix") or "homeassistant"),
            )
        except TelegramVoipApiError as err:
            raise HomeAssistantError(str(err)) from err
        data = dict(self.coordinator.data or {})
        if result.get("mqtt"):
            data["mqtt"] = result["mqtt"]
        self.coordinator.async_set_updated_data(data)
