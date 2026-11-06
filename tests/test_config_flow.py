from __future__ import annotations

from homeassistant import config_entries, data_entry_flow
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calling_messenger_hub.api import (
    TelegramVoipApi,
    TelegramVoipAuthError,
    TelegramVoipConnectionError,
)
from custom_components.calling_messenger_hub.const import (
    CONF_NOTIFY_EVENTS,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_URL,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_NOTIFY_EVENTS,
    DOMAIN,
)


async def test_user_flow_creates_entry(hass, monkeypatch):
    async def fake_status(self):
        return {"accounts": []}

    monkeypatch.setattr(TelegramVoipApi, "async_status", fake_status)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "hub.local:3030",
            CONF_TOKEN: " token ",
            CONF_SCAN_INTERVAL: 45,
        },
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_URL: "http://hub.local:3030",
        CONF_TOKEN: "token",
    }
    assert result["options"] == {CONF_SCAN_INTERVAL: 45}


async def test_user_flow_rejects_invalid_auth(hass, monkeypatch):
    async def fake_status(self):
        raise TelegramVoipAuthError("invalid")

    monkeypatch.setattr(TelegramVoipApi, "async_status", fake_status)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "hub.local", CONF_TOKEN: "bad", CONF_SCAN_INTERVAL: 30},
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_rejects_connection_error(hass, monkeypatch):
    async def fake_status(self):
        raise TelegramVoipConnectionError("offline")

    monkeypatch.setattr(TelegramVoipApi, "async_status", fake_status)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "hub.local", CONF_TOKEN: "token", CONF_SCAN_INTERVAL: 30},
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_url_aborts(hass, monkeypatch):
    async def fake_status(self):
        return {"accounts": []}

    monkeypatch.setattr(TelegramVoipApi, "async_status", fake_status)
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="http://hub.local:3030",
        data={CONF_URL: "http://hub.local:3030", CONF_TOKEN: "token"},
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://hub.local:3030", CONF_TOKEN: "token", CONF_SCAN_INTERVAL: 30},
    )
    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_updates_notifications(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://hub.local:3030", CONF_TOKEN: "token"},
        options={CONF_SCAN_INTERVAL: 30},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL: 60,
            CONF_NOTIFY_SERVICE: "notify.mobile_app_phone",
            CONF_NOTIFY_EVENTS: ["alert", "sms"],
            CONF_NOTIFY_URL: "/lovelace/calls",
        },
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SCAN_INTERVAL: 60,
        CONF_NOTIFY_SERVICE: "notify.mobile_app_phone",
        CONF_NOTIFY_EVENTS: ["alert", "sms"],
        CONF_NOTIFY_URL: "/lovelace/calls",
    }


async def test_options_flow_defaults_notifications(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://hub.local:3030", CONF_TOKEN: "token"},
        options={CONF_SCAN_INTERVAL: 30},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SCAN_INTERVAL: 45},
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SCAN_INTERVAL: 45,
        CONF_NOTIFY_SERVICE: "",
        CONF_NOTIFY_EVENTS: DEFAULT_NOTIFY_EVENTS,
        CONF_NOTIFY_URL: "",
    }
