from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import TelegramVoipCoordinator


def account_by_id(data: dict[str, Any], account_id: str) -> dict[str, Any]:
    for account in data.get("accounts") or []:
        if str(account.get("id")) == account_id:
            return account
    return {}


def account_device_info(
    coordinator: TelegramVoipCoordinator,
    entry: ConfigEntry,
    account: dict[str, Any],
) -> DeviceInfo:
    service = str(account.get("service") or "telegram")
    name = str(account.get("name") or account.get("phone") or account.get("id"))
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{account.get('id')}")},
        name=name,
        manufacturer="apk-lab",
        model=str(account.get("driver_label") or account.get("channel") or service.upper()),
        via_device=(DOMAIN, entry.entry_id),
        configuration_url=coordinator.api.base_url,
    )


class AccountEntityRegistry:
    def __init__(
        self,
        coordinator: TelegramVoipCoordinator,
        add_entities: Callable[[list[Entity]], None],
        factory: Callable[[dict[str, Any]], list[tuple[str, Entity]]],
    ) -> None:
        self._coordinator = coordinator
        self._add_entities = add_entities
        self._factory = factory
        self._entities: dict[str, Entity] = {}
        self._remove_listener = coordinator.async_add_listener(self._sync)
        self._sync()

    @callback
    def async_stop(self) -> None:
        self._remove_listener()

    @callback
    def _sync(self) -> None:
        desired: set[str] = set()
        new_entities: list[Entity] = []
        for account in self._coordinator.data.get("accounts") or []:
            account_id = str(account.get("id") or "")
            if not account_id:
                continue
            for key, entity in self._factory(account):
                desired.add(key)
                if key not in self._entities:
                    self._entities[key] = entity
                    new_entities.append(entity)
        for key in list(self._entities):
            if key not in desired:
                self._entities.pop(key).async_remove()
        if new_entities:
            self._add_entities(new_entities)
