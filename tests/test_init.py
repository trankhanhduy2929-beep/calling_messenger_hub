from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calling_messenger_hub.api import TelegramVoipApi
from custom_components.calling_messenger_hub.const import (
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    DOMAIN,
)
from custom_components.calling_messenger_hub.stream import event_signal

STATUS = {
    "accounts": [
        {
            "id": "tg-1",
            "name": "Telegram Personal",
            "service": "telegram",
            "channel": "telegram",
            "state": "online",
            "phone": "+10000000001",
        },
        {
            "id": "sim-1",
            "name": "SIM Lab",
            "service": "sim",
            "channel": "modem",
            "driver": "quectel",
            "driver_label": "Quectel EC25",
            "state": "online",
            "phone": "+10000000002",
            "signal_percent": 73,
            "signal_dbm": -61,
            "carrier": "Lab Mobile",
            "network": "LTE",
            "balance": "12.50 USD",
            "expiry": "2027-01-01",
        },
    ],
    "calls": [],
    "rings": [],
    "alerts": [],
    "messages": [],
}


async def test_setup_creates_base_and_per_account_entities(hass, monkeypatch):
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
        entry_id="entry",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    unique_ids = {
        item.unique_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert "entry_accounts_online" in unique_ids
    assert "entry_activity" in unique_ids
    assert "entry_tg-1_online" in unique_ids
    assert "entry_sim-1_online" in unique_ids
    assert "entry_sim-1_signal" in unique_ids
    assert "entry_sim-1_carrier" in unique_ids
    assert "entry_sim-1_balance" in unique_ids
    assert "entry_sim-1_expiry" in unique_ids
    assert "entry_tg-1_signal" not in unique_ids

    signal_entry = next(
        item for item in registry.entities.values()
        if item.unique_id == "entry_sim-1_signal"
    )
    assert hass.states.get(signal_entry.entity_id).state == "73"

    event_entry = next(
        item for item in registry.entities.values()
        if item.unique_id == "entry_activity"
    )
    async_dispatcher_send(
        hass,
        event_signal(entry.entry_id),
        {
            "id": "sms-1",
            "kind": "sms",
            "message": "New SMS",
            "account_id": "sim-1",
            "ts": "2026-01-01T00:00:00Z",
        },
    )
    await hass.async_block_till_done()
    event_state = hass.states.get(event_entry.entity_id)
    assert event_state.attributes["event_type"] == "sms"
    assert event_state.attributes["message"] == "New SMS"
    assert event_state.attributes["account_id"] == "sim-1"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
