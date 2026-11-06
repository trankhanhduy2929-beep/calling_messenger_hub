from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TelegramVoipCoordinator
from .stream import TelegramVoipEventStream, stream_status_signal


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


class TelegramVoipStreamEntity(TelegramVoipEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._stream: TelegramVoipEventStream = entry.runtime_data.stream

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                stream_status_signal(self._entry.entry_id),
                self._handle_stream_status,
            )
        )

    @callback
    def _handle_stream_status(self) -> None:
        self.async_write_ha_state()
