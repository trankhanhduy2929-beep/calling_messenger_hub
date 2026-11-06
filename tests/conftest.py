from __future__ import annotations

import asyncio

import pytest

from custom_components.calling_messenger_hub.api import TelegramVoipApi

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def mock_event_stream(monkeypatch):
    async def fake_stream(self):
        await asyncio.Event().wait()
        yield {}

    monkeypatch.setattr(TelegramVoipApi, "async_stream_events", fake_stream)
