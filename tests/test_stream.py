from __future__ import annotations

import asyncio

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calling_messenger_hub.const import (
    CONF_TOKEN,
    CONF_URL,
    DOMAIN,
)
from custom_components.calling_messenger_hub.stream import (
    TelegramVoipEventStream,
    event_signal,
)


class FakeApi:
    def __init__(self, events):
        self.events = events

    async def async_stream_events(self):
        for item in self.events:
            yield item
        await asyncio.Event().wait()


class FakeCoordinator:
    def __init__(self):
        self.refreshes = 0

    async def async_request_refresh(self):
        self.refreshes += 1


async def test_stream_dispatches_events_once(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://hub.local:3030", CONF_TOKEN: "token"},
        entry_id="stream-entry",
    )
    entry.add_to_hass(hass)
    api = FakeApi(
        [
            {"id": "evt-1", "kind": "sms", "message": "New SMS", "ts": "2026-01-01T00:00:00Z"},
            {"id": "evt-1", "kind": "sms", "message": "New SMS", "ts": "2026-01-01T00:00:00Z"},
        ]
    )
    coordinator = FakeCoordinator()
    stream = TelegramVoipEventStream(hass, entry, api, coordinator)
    received = []
    connected = []
    ready = asyncio.Event()

    def _listen(event):
        received.append(event)
        connected.append(stream.connected)
        ready.set()

    unsub = async_dispatcher_connect(hass, event_signal(entry.entry_id), _listen)
    stream.async_start()
    try:
        await asyncio.wait_for(ready.wait(), timeout=2)
        await hass.async_block_till_done()
    finally:
        await stream.async_stop()
        unsub()

    assert [item["id"] for item in received] == ["evt-1"]
    assert connected == [True]
