from __future__ import annotations

from types import SimpleNamespace

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.calling_messenger_hub.const import DOMAIN
from custom_components.calling_messenger_hub.notifications import (
    ACTION_CALLBACK,
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

async def test_notification_skips_callback_for_telegram_call(hass):
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

    titles = [item["title"] for item in service[0].data["data"]["actions"]]
    assert titles == ["Đã xử lý", "Tắt chuông"]

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
