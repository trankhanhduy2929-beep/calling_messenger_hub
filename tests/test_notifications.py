from __future__ import annotations

from datetime import time as dt_time
from types import SimpleNamespace

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.calling_messenger_hub import notifications
from custom_components.calling_messenger_hub.const import DOMAIN
from custom_components.calling_messenger_hub.notifications import (
    ACTION_CALLBACK,
    ACTION_OPEN_CHAT,
    NOTIFICATION_ACTION_EVENT,
    async_notify_event,
    async_register_notification_actions,
    async_unregister_notification_actions,
    should_notify,
)


def _entry(**options):
    return MockConfigEntry(
        domain=DOMAIN,
        data={},
        options=options,
        entry_id="notify-entry",
    )


async def test_should_notify_filters_selected_event_types(hass):
    entry = _entry(
        notify_service="notify.mobile_app_phone",
        notify_events=["alert", "sms"],
    )

    assert should_notify(entry, {"kind": "sms", "sender": "+100"})
    assert should_notify(entry, {"kind": "alert", "alert_id": "alert-1"})
    assert not should_notify(entry, {"kind": "sms"})
    assert not should_notify(
        entry, {"kind": "alert", "alert_id": "alert-1", "status": "resolved"}
    )
    assert not should_notify(entry, {"kind": "call", "call_id": "call-1"})


async def test_notification_contains_actions_and_hangup(hass):
    entry = _entry(
        notify_service="notify.mobile_app_phone",
        notify_events=["alert"],
        notify_url="/lovelace/calls",
    )
    service = async_mock_service(hass, "notify", "mobile_app_phone")

    await async_notify_event(
        hass,
        entry,
        {
            "id": "evt-1",
            "kind": "alert",
            "alert_id": "alert-1",
            "call_id": "call-1",
            "account_id": "sim-1",
            "severity": "critical",
            "message": "Cửa đang mở",
        },
    )
    await hass.async_block_till_done()

    assert len(service) == 1
    data = service[0].data
    assert data["title"] == "Báo động · Nghiêm trọng"
    assert data["message"] == "Cửa đang mở"
    actions = data["data"]["actions"]
    assert [item["title"] for item in actions] == ["Đã xử lý", "Tắt chuông", "Mở"]
    assert actions[0]["action"].startswith("CMH_ACK|notify-entry|alert-1|")
    assert actions[1]["action"].startswith("CMH_HANGUP|notify-entry||call-1|sim-1|")
    assert actions[2]["uri"] == "/lovelace/calls"


async def test_notification_adds_callback_for_sms_sender(hass):
    entry = _entry(
        notify_service="notify.mobile_app_phone",
        notify_events=["sms"],
    )
    service = async_mock_service(hass, "notify", "mobile_app_phone")

    await async_notify_event(
        hass,
        entry,
        {
            "id": "evt-3",
            "kind": "sms",
            "sender": "+84 901 234 567",
            "message": "New SMS",
        },
    )
    await hass.async_block_till_done()

    actions = service[0].data["data"]["actions"]
    assert [item["title"] for item in actions] == ["Đã xử lý", "Gọi lại"]
    assert actions[1] == {
        "action": ACTION_CALLBACK,
        "title": "Gọi lại",
        "uri": "tel:+84901234567",
    }


async def test_notification_skips_callback_for_zalo_sms(hass):
    entry = _entry(
        notify_service="notify.mobile_app_phone",
        notify_events=["sms"],
        notify_accounts="zalo",
    )
    entry.runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data={
                "accounts": [{"id": "zalo-1", "service": "zalo"}],
                "calls": [],
                "rings": [],
            }
        )
    )
    service = async_mock_service(hass, "notify", "mobile_app_phone")

    await async_notify_event(
        hass,
        entry,
        {
            "id": "evt-zalo",
            "kind": "sms",
            "account_id": "zalo-1",
            "sender": "+84901234567",
            "message": "Zalo message",
        },
    )
    await hass.async_block_till_done()

    actions = service[0].data["data"]["actions"]
    assert [item["title"] for item in actions] == ["Đã xử lý"]


async def test_notification_adds_callback_for_sim_call(hass):
    entry = _entry(
        notify_service="notify.mobile_app_phone",
        notify_events=["call"],
    )
    entry.runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data={
                "accounts": [{"id": "sim-1", "service": "sim"}],
                "calls": [
                    {
                        "id": "call-1",
                        "account_id": "sim-1",
                        "service": "sim",
                        "peer_id": "0912345678",
                    }
                ],
            }
        )
    )
    service = async_mock_service(hass, "notify", "mobile_app_phone")

    await async_notify_event(
        hass,
        entry,
        {
            "id": "evt-4",
            "kind": "call",
            "call_id": "call-1",
            "account_id": "sim-1",
            "message": "Bắt đầu gọi",
        },
    )
    await hass.async_block_till_done()

    actions = service[0].data["data"]["actions"]
    assert [item["title"] for item in actions] == [
        "Đã xử lý",
        "Gọi lại",
        "Tắt chuông",
    ]
    assert actions[1]["uri"] == "tel:0912345678"
    assert actions[2]["action"].startswith("CMH_HANGUP|notify-entry||call-1|sim-1|")


async def test_notification_adds_telegram_chat_action(hass):
    entry = _entry(
        notify_service="notify.mobile_app_phone",
        notify_events=["call"],
    )
    entry.runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data={
                "accounts": [{"id": "tg-1", "service": "telegram"}],
                "calls": [
                    {
                        "id": "call-2",
                        "account_id": "tg-1",
                        "peer_id": 123456789,
                    }
                ],
            }
        )
    )
    service = async_mock_service(hass, "notify", "mobile_app_phone")

    await async_notify_event(
        hass,
        entry,
        {
            "id": "evt-5",
            "kind": "call",
            "call_id": "call-2",
            "account_id": "tg-1",
            "message": "Bắt đầu gọi",
        },
    )
    await hass.async_block_till_done()

    actions = service[0].data["data"]["actions"]
    assert [item["title"] for item in actions] == [
        "Đã xử lý",
        "Mở chat",
        "Tắt chuông",
    ]
    assert actions[1] == {
        "action": ACTION_OPEN_CHAT,
        "title": "Mở chat",
        "uri": "tg://user?id=123456789",
    }


async def test_notification_uses_telegram_username_for_chat(hass):
    entry = _entry(
        notify_service="notify.mobile_app_phone",
        notify_events=["message"],
    )
    entry.runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data={
                "accounts": [{"id": "tg-1", "service": "telegram"}],
                "calls": [],
                "rings": [],
            }
        )
    )
    service = async_mock_service(hass, "notify", "mobile_app_phone")

    await async_notify_event(
        hass,
        entry,
        {
            "id": "evt-chat",
            "kind": "message",
            "account_id": "tg-1",
            "peer_name": "@friend",
            "peer_id": 123456789,
        },
    )
    await hass.async_block_till_done()

    actions = service[0].data["data"]["actions"]
    assert actions[1]["uri"] == "https://t.me/friend"


async def test_notification_uses_zalo_chat_action(hass):
    entry = _entry(
        notify_service="notify.mobile_app_phone",
        notify_events=["message"],
    )
    entry.runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data={
                "accounts": [{"id": "zalo-1", "service": "zalo"}],
                "calls": [],
                "rings": [],
            }
        )
    )
    service = async_mock_service(hass, "notify", "mobile_app_phone")

    await async_notify_event(
        hass,
        entry,
        {
            "id": "evt-zalo-chat",
            "kind": "message",
            "account_id": "zalo-1",
            "peer_id": "123456789012345678",
        },
    )
    await hass.async_block_till_done()

    actions = service[0].data["data"]["actions"]
    assert actions[1]["uri"] == "https://zalo.me/123456789012345678"


async def test_notification_routes_to_multiple_services(hass):
    entry = _entry(
        notify_services="notify.mobile_app_phone\nnotify.mobile_app_tablet",
        notify_events=["sms"],
    )
    phone = async_mock_service(hass, "notify", "mobile_app_phone")
    tablet = async_mock_service(hass, "notify", "mobile_app_tablet")

    await async_notify_event(
        hass,
        entry,
        {"id": "evt-multi", "kind": "sms", "sender": "+100", "message": "hello"},
    )
    await hass.async_block_till_done()

    assert len(phone) == 1
    assert len(tablet) == 1


async def test_critical_events_use_critical_services(hass):
    entry = _entry(
        notify_services="notify.mobile_app_phone,notify.mobile_app_tablet",
        notify_critical_services="notify.mobile_app_critical",
        notify_events=["alert"],
    )
    phone = async_mock_service(hass, "notify", "mobile_app_phone")
    tablet = async_mock_service(hass, "notify", "mobile_app_tablet")
    critical = async_mock_service(hass, "notify", "mobile_app_critical")

    await async_notify_event(
        hass,
        entry,
        {
            "id": "evt-critical",
            "kind": "alert",
            "alert_id": "alert-critical",
            "severity": "critical",
        },
    )
    await async_notify_event(
        hass,
        entry,
        {
            "id": "evt-warning",
            "kind": "alert",
            "alert_id": "alert-warning",
            "severity": "warning",
        },
    )
    await hass.async_block_till_done()

    assert len(critical) == 1
    assert len(phone) == 1
    assert len(tablet) == 1


async def test_account_and_severity_filters_with_quiet_hours(hass):
    entry = _entry(
        notify_service="notify.mobile_app_phone",
        notify_events=["sms"],
        notify_accounts="Telegram Main",
        notify_severities=["critical"],
        notify_quiet_start="22:00",
        notify_quiet_end="06:00",
    )
    entry.runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data={
                "accounts": [
                    {"id": "tg-1", "name": "Telegram Main", "service": "telegram"}
                ],
                "calls": [],
                "rings": [],
            }
        )
    )

    critical = {
        "kind": "sms",
        "account_id": "tg-1",
        "sender": "+100",
        "severity": "critical",
    }
    warning = {**critical, "severity": "warning"}
    other_account = {**critical, "account_id": "tg-2"}

    assert should_notify(entry, critical, now=dt_time(12, 0))
    assert should_notify(entry, critical, now=dt_time(23, 0))
    assert not should_notify(entry, warning, now=dt_time(12, 0))
    assert not should_notify(entry, other_account, now=dt_time(12, 0))


async def test_notification_cooldown_suppresses_duplicates(hass, monkeypatch):
    entry = _entry(
        notify_service="notify.mobile_app_phone",
        notify_events=["sms"],
        notify_cooldown=60,
    )
    service = async_mock_service(hass, "notify", "mobile_app_phone")
    clock = {"now": 100.0}
    monkeypatch.setattr(notifications.time, "monotonic", lambda: clock["now"])

    event = {"kind": "sms", "sender": "+100", "message": "hello"}
    await async_notify_event(hass, entry, event)
    clock["now"] = 120.0
    await async_notify_event(hass, entry, event)
    clock["now"] = 161.0
    await async_notify_event(hass, entry, event)
    await hass.async_block_till_done()

    assert len(service) == 2


async def test_notification_is_skipped_without_service(hass):
    entry = _entry(notify_events=["sms"])
    service = async_mock_service(hass, "notify", "mobile_app_phone")

    await async_notify_event(
        hass,
        entry,
        {"id": "evt-2", "kind": "sms", "sender": "+100", "message": "hello"},
    )
    await hass.async_block_till_done()

    assert service == []


async def test_uri_only_notification_actions_are_ignored(hass):
    async_register_notification_actions(hass)
    received = []
    unsub = hass.bus.async_listen(
        NOTIFICATION_ACTION_EVENT,
        lambda event: received.append(event.data),
    )
    try:
        for action in (ACTION_OPEN_CHAT, ACTION_CALLBACK):
            hass.bus.async_fire(
                "mobile_app_notification_action",
                {"action": action},
            )
        await hass.async_block_till_done()
    finally:
        unsub()
        async_unregister_notification_actions(hass)

    assert received == []


async def test_notification_action_event_is_forwarded(hass):
    async_register_notification_actions(hass)
    received = []
    unsub = hass.bus.async_listen(
        NOTIFICATION_ACTION_EVENT,
        lambda event: received.append(event.data),
    )
    try:
        hass.bus.async_fire(
            "mobile_app_notification_action",
            {"action": "CMH_ACK|entry-1|alert-1|evt-1||cmh_tag"},
        )
        await hass.async_block_till_done()
    finally:
        unsub()
        async_unregister_notification_actions(hass)

    assert received == [
        {
            "action": "CMH_ACK",
            "entry_id": "entry-1",
            "alert_id": "alert-1",
            "item_id": "evt-1",
            "account_id": "",
            "tag": "cmh_tag",
        }
    ]
