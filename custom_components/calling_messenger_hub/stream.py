from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import (
    TelegramVoipApi,
    TelegramVoipApiError,
    TelegramVoipAuthError,
    TelegramVoipConnectionError,
)
from .const import DOMAIN
from .coordinator import TelegramVoipCoordinator
from .notifications import async_notify_event, should_notify

_LOGGER = logging.getLogger(__name__)

REFRESH_KINDS = {"account", "alert", "call", "otp", "ring", "sms"}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def event_signal(entry_id: str) -> str:
    return f"{DOMAIN}_event_{entry_id}"


def stream_status_signal(entry_id: str) -> str:
    return f"{DOMAIN}_stream_{entry_id}"


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
        self._restart_lock = asyncio.Lock()
        self._connected = False
        self._connected_since: str | None = None
        self._last_event_at: str | None = None
        self._last_event_id: str | None = None
        self._last_event_kind: str | None = None
        self._last_error: str | None = None
        self._events_received = 0
        self._reconnects = 0
        self._refresh_pending = False
        self._seen_ids: deque[str] = deque(maxlen=500)
        self._seen_set: set[str] = set()

    @property
    def connected(self) -> bool:
        return self._connected

    def snapshot(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "connected_since": self._connected_since,
            "last_event_at": self._last_event_at,
            "last_event_id": self._last_event_id,
            "last_event_kind": self._last_event_kind,
            "last_error": self._last_error,
            "events_received": self._events_received,
            "reconnects": self._reconnects,
        }

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
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self._connected:
            self._connected = False
            self._connected_since = None
            self._notify_status()

    async def async_restart(self) -> None:
        async with self._restart_lock:
            await self.async_stop()
            self.async_start()

    async def _run(self) -> None:
        delay = 1
        attempt = 0
        while True:
            if attempt:
                self._reconnects += 1
                self._notify_status()
            attempt += 1
            try:
                async for event in self._api.async_stream_events(
                    on_connect=self._mark_connected
                ):
                    delay = 1
                    self._dispatch(event)
            except TelegramVoipAuthError as err:
                self._last_error = f"invalid API token: {err}"
                _LOGGER.warning("Calling Messenger Hub rejected the API token: %s", err)
                delay = 30
            except (TelegramVoipConnectionError, TelegramVoipApiError) as err:
                self._last_error = str(err)
                if self._connected:
                    _LOGGER.warning("Calling Messenger Hub event stream lost: %s", err)
                else:
                    _LOGGER.debug("Calling Messenger Hub event stream unavailable: %s", err)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self._last_error = str(err)
                _LOGGER.exception("Calling Messenger Hub event stream failed")
            finally:
                if self._connected:
                    self._connected = False
                    self._connected_since = None
                    self._notify_status()
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)

    @callback
    def _mark_connected(self) -> None:
        self._connected = True
        self._connected_since = utc_now()
        self._last_error = None
        self._notify_status()

    def _dispatch(self, event: dict[str, Any]) -> None:
        event_id = str(event.get("id") or "").strip()
        if event_id:
            if event_id in self._seen_set:
                return
            if len(self._seen_ids) == self._seen_ids.maxlen:
                self._seen_set.discard(self._seen_ids[0])
            self._seen_ids.append(event_id)
            self._seen_set.add(event_id)
        self._events_received += 1
        self._last_event_at = str(event.get("ts") or utc_now())
        self._last_event_id = event_id or None
        self._last_event_kind = str(event.get("kind") or "") or None
        async_dispatcher_send(self._hass, event_signal(self._entry.entry_id), event)
        self._notify_status()
        if str(event.get("kind") or "") in REFRESH_KINDS:
            self._request_refresh()
        if should_notify(self._entry, event):
            self._hass.async_create_task(self._async_notify(event))

    async def _async_notify(self, event: dict[str, Any]) -> None:
        try:
            await async_notify_event(self._hass, self._entry, event)
        except Exception:
            _LOGGER.exception("Cannot dispatch Calling Messenger Hub notification")

    @callback
    def _notify_status(self) -> None:
        async_dispatcher_send(
            self._hass,
            stream_status_signal(self._entry.entry_id),
        )

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
