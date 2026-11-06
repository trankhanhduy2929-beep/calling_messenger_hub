from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import (
    TelegramVoipApi,
    TelegramVoipApiError,
    TelegramVoipAuthError,
    TelegramVoipConnectionError,
)
from .const import DOMAIN
from .coordinator import TelegramVoipCoordinator

_LOGGER = logging.getLogger(__name__)

REFRESH_KINDS = {"account", "alert", "call", "otp", "ring", "sms"}


def event_signal(entry_id: str) -> str:
    return f"{DOMAIN}_event_{entry_id}"


class TelegramVoipEventStream:
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: TelegramVoipApi,
        coordinator: TelegramVoipCoordinator,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._api = api
        self._coordinator = coordinator
        self._task: asyncio.Task[Any] | None = None
        self._connected = False
        self._refresh_pending = False
        self._seen_ids: deque[str] = deque(maxlen=500)
        self._seen_set: set[str] = set()

    @property
    def connected(self) -> bool:
        return self._connected

    def async_start(self) -> None:
        if self._task is None:
            self._task = self._entry.async_create_background_task(
                self._hass,
                self._run(),
                f"{DOMAIN}_events_{self._entry.entry_id}",
            )

    async def async_stop(self) -> None:
        task = self._task
        self._task = None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _run(self) -> None:
        delay = 1
        while True:
            try:
                async for event in self._api.async_stream_events():
                    if not self._connected:
                        self._connected = True
                        _LOGGER.debug("Calling Messenger Hub event stream connected")
                    delay = 1
                    self._dispatch(event)
            except TelegramVoipAuthError as err:
                _LOGGER.warning("Calling Messenger Hub rejected the API token: %s", err)
                delay = 30
            except (TelegramVoipConnectionError, TelegramVoipApiError) as err:
                if self._connected:
                    _LOGGER.warning("Calling Messenger Hub event stream lost: %s", err)
                else:
                    _LOGGER.debug("Calling Messenger Hub event stream unavailable: %s", err)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("Calling Messenger Hub event stream failed")
            finally:
                self._connected = False
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)

    def _dispatch(self, event: dict[str, Any]) -> None:
        event_id = str(event.get("id") or "").strip()
        if event_id:
            if event_id in self._seen_set:
                return
            if len(self._seen_ids) == self._seen_ids.maxlen:
                self._seen_set.discard(self._seen_ids[0])
            self._seen_ids.append(event_id)
            self._seen_set.add(event_id)
        async_dispatcher_send(self._hass, event_signal(self._entry.entry_id), event)
        if str(event.get("kind") or "") in REFRESH_KINDS:
            self._request_refresh()

    def _request_refresh(self) -> None:
        if self._refresh_pending:
            return
        self._refresh_pending = True
        self._hass.async_create_task(self._refresh_later())

    async def _refresh_later(self) -> None:
        await asyncio.sleep(0.5)
        try:
            await self._coordinator.async_request_refresh()
        finally:
            self._refresh_pending = False
