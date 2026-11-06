from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    async_add_entities(
        [
            RefreshButton(coordinator, entry),
            CheckUpdateButton(coordinator, entry),
        ]
    )

class TelegramVoipButton(TelegramVoipEntity, ButtonEntity):
    pass

class RefreshButton(TelegramVoipButton):
    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()

class CheckUpdateButton(TelegramVoipButton):
    _attr_translation_key = "check_update"
    _attr_icon = "mdi:update"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_check_update"

    async def async_press(self) -> None:
        try:
            result = await self.coordinator.api.async_check_update()
        except TelegramVoipApiError as err:
            raise HomeAssistantError(str(err)) from err
        data = dict(self.coordinator.data or {})
        data["update"] = result
        self.coordinator.async_set_updated_data(data)
