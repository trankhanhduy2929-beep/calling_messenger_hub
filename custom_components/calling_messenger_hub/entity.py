from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TelegramVoipCoordinator


class TelegramVoipEntity(CoordinatorEntity[TelegramVoipCoordinator]):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = device_info or DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Calling Messenger Hub",
            manufacturer="apk-lab",
            model="Calling & messaging hub",
            configuration_url=coordinator.api.base_url,
        )
