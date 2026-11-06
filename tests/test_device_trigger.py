from __future__ import annotations

import asyncio

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calling_messenger_hub.api import TelegramVoipApi
from custom_components.calling_messenger_hub.const import (
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    DOMAIN,
)
from custom_components.calling_messenger_hub.device_trigger import (
    async_attach_trigger,
    async_get_triggers,
)
from custom_components.calling_messenger_hub.event import EVENT_TYPES
from custom_components.calling_messenger_hub.stream import event_signal

STATUS = {"accounts": [], "calls": [], "rings": [], "alerts": [], "messages": []}


async def _setup_entry(hass, monkeypatch):
    async def fake_status(self):
        return STATUS

    async def fake_stream(self, on_connect=None):
        if on_connect is not None:
            on_connect()
        await asyncio.Event().wait()
        yield {}

    monkeypatch.setattr(TelegramVoipApi, "async_status", fake_status)
    monkeypatch.setattr(TelegramVoipApi, "async_stream_events", fake_stream)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://hub.local:3030", CONF_TOKEN: "token"},
        options={CONF_SCAN_INTERVAL: 30},
        entry_id="trigger-entry",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, entry.entry_id)}
    )
    assert device is not None
    return entry, device


async def test_device_triggers_expose_all_event_types(hass, monkeypatch):
    entry, device = await _setup_entry(hass, monkeypatch)
    try:
        triggers = await async_get_triggers(hass, device.id)
        assert {item[CONF_TYPE] for item in triggers} == set(EVENT_TYPES)
        assert all(item[CONF_DEVICE_ID] == device.id for item in triggers)
    finally:
        await hass.config_entries.async_unload(entry.entry_id)


async def test_device_trigger_fires_on_matching_kind(hass, monkeypatch):
    entry, device = await _setup_entry(hass, monkeypatch)
    calls = []

    async def action(variables, context=None):
        calls.append(variables)

    config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: "sms",
    }
    unsub = await async_attach_trigger(
        hass,
        config,
        action,
        {"trigger_data": {"id": "0", "idx": "0", "alias": None}},
    )
    try:
        async_dispatcher_send(
            hass,
            event_signal(entry.entry_id),
            {"id": "evt-1", "kind": "call", "call_id": "call-1"},
        )
        async_dispatcher_send(
            hass,
            event_signal(entry.entry_id),
            {"id": "evt-2", "kind": "sms", "sender": "+100", "message": "hello"},
        )
        await hass.async_block_till_done()
        assert len(calls) == 1
        assert calls[0]["trigger"]["type"] == "sms"
        assert calls[0]["trigger"]["event"]["id"] == "evt-2"
    finally:
        unsub()
        await hass.config_entries.async_unload(entry.entry_id)
