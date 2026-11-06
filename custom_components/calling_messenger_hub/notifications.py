from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import Event, HomeAssistant, callback

from .api import TelegramVoipApiError
from .const import (
    CONF_NOTIFY_EVENTS,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_URL,
    DEFAULT_NOTIFY_EVENTS,
    DOMAIN,
    NOTIFICATION_ACTION_EVENT,
)

_LOGGER = logging.getLogger(__name__)

NOTIFY_DOMAIN = "notify"
MOBILE_APP_ACTION_EVENT = "mobile_app_notification_action"
ACTION_ACK = "CMH_ACK"
ACTION_HANGUP = "CMH_HANGUP"
ACTION_OPEN = "CMH_OPEN"
ACTION_CALLBACK = "CMH_CALLBACK"
_PHONE_RE = re.compile(r"^\+?\d{5,15}$")
DATA_NOTIFICATION_ACTIONS = f"{DOMAIN}_notification_actions"

_TITLES = {
    "alert": "Báo động",
    "sms": "SMS mới",
    "otp": "OTP mới",
    "call": "Cuộc gọi",
    "ring": "Chuông báo động",
    "account": "Tài khoản",
    "message": "Tin nhắn mới",
}

_SEVERITIES = {
    "info": "Thông tin",
    "warning": "Cảnh báo",
    "critical": "Nghiêm trọng",
}


def _notify_service(options: dict[str, Any]) -> str | None:
    value = str(options.get(CONF_NOTIFY_SERVICE) or "").strip()
    if not value:
        return None
    if value.startswith(f"{NOTIFY_DOMAIN}."):
        value = value.split(".", 1)[1]
    return value or None


def _event_tag(entry: ConfigEntry, event: dict[str, Any]) -> str:
    item = str(
        event.get("id")
        or event.get("alert_id")
        or event.get("call_id")
        or event.get("ring_id")
        or event.get("ts")
        or event.get("kind")
        or "event"
    )
    return f"cmh_{entry.entry_id}_{item}"[:200]


def _action(prefix: str, *parts: Any) -> str:
    return "|".join([prefix, *(str(part or "") for part in parts)])

def _phone_uri(value: Any) -> str | None:
    text = re.sub(r"[\s().-]+", "", str(value or "").strip())
    if not _PHONE_RE.fullmatch(text):
        return None
    return f"tel:{text}"

def _coordinator_data(entry: ConfigEntry) -> dict[str, Any]:
    runtime = getattr(entry, "runtime_data", None)
    coordinator = getattr(runtime, "coordinator", None)
    data = getattr(coordinator, "data", None)
    return dict(data) if isinstance(data, dict) else {}

def _account_service(entry: ConfigEntry, account_id: str) -> str:
    for account in _coordinator_data(entry).get("accounts") or []:
        if str(account.get("id") or "") == account_id:
            return str(account.get("service") or "")
    return ""

def _event_item(entry: ConfigEntry, event: dict[str, Any]) -> dict[str, Any]:
    data = _coordinator_data(entry)
    call_id = str(event.get("call_id") or "")
    ring_id = str(event.get("ring_id") or "")
    for key in ("calls", "rings"):
        for item in data.get(key) or []:
            item_id = str(item.get("id") or "")
            if (call_id and item_id == call_id) or (ring_id and item_id == ring_id):
                return dict(item)
    return {}

def _callback_target(entry: ConfigEntry, event: dict[str, Any]) -> str | None:
    kind = str(event.get("kind") or "")
    if kind in {"sms", "otp"}:
        return _phone_uri(
            event.get("sender") or event.get("peer_id") or event.get("from")
        )
    if kind not in {"call", "ring"}:
        return None
    item = _event_item(entry, event)
    account_id = str(event.get("account_id") or item.get("account_id") or "")
    service = str(
        event.get("service")
        or item.get("service")
        or _account_service(entry, account_id)
    )
    if service != "sim":
        return None
    return _phone_uri(
        item.get("peer_id")
        or item.get("to")
        or event.get("peer_id")
        or event.get("to")
    )


def should_notify(entry: ConfigEntry, event: dict[str, Any]) -> bool:
    if _notify_service(entry.options) is None:
        return False
    kind = str(event.get("kind") or "")
    selected = set(entry.options.get(CONF_NOTIFY_EVENTS) or DEFAULT_NOTIFY_EVENTS)
    if kind not in selected:
        return False
    if kind == "alert":
        return bool(event.get("alert_id")) and not event.get("status")
    if kind in {"sms", "otp"}:
        return bool(event.get("sender"))
    return True


def _notification_actions(
    entry: ConfigEntry,
    event: dict[str, Any],
    url: str,
) -> list[dict[str, str]]:
    tag = _event_tag(entry, event)
    actions: list[dict[str, str]] = [
        {
            "action": _action(
                ACTION_ACK,
                entry.entry_id,
                event.get("alert_id"),
                event.get("id"),
                "",
                tag,
            ),
            "title": "Đã xử lý",
        }
    ]
    callback = _callback_target(entry, event)
    if callback:
        actions.append(
            {
                "action": ACTION_CALLBACK,
                "title": "Gọi lại",
                "uri": callback,
            }
        )
    item_id = event.get("call_id") or event.get("ring_id")
    if item_id:
        actions.append(
            {
                "action": _action(
                    ACTION_HANGUP,
                    entry.entry_id,
                    "",
                    item_id,
                    event.get("account_id"),
                    tag,
                ),
                "title": "Tắt chuông",
            }
        )
    if url:
        actions.append(
            {
                "action": ACTION_OPEN,
                "title": "Mở",
                "uri": url,
            }
        )
    return actions[:3]


def _title(kind: str, event: dict[str, Any]) -> str:
    title = _TITLES.get(kind, "Calling Messenger Hub")
    severity = _SEVERITIES.get(str(event.get("severity") or ""))
    if kind == "alert" and severity:
        return f"{title} · {severity}"
    return title


async def async_notify_event(
    hass: HomeAssistant,
    entry: ConfigEntry,
    event: dict[str, Any],
) -> None:
    if not should_notify(entry, event):
        return
    service = _notify_service(entry.options)
    if service is None or not hass.services.has_service(NOTIFY_DOMAIN, service):
        _LOGGER.debug("Notification service notify.%s is not available", service)
        return
    kind = str(event.get("kind") or "other")
    tag = _event_tag(entry, event)
    payload = {
        "title": _title(kind, event),
        "message": str(event.get("message") or _TITLES.get(kind) or kind),
        "data": {
            "tag": tag,
            "group": f"{DOMAIN}_{kind}",
            "actions": _notification_actions(
                entry,
                event,
                str(entry.options.get(CONF_NOTIFY_URL) or "").strip(),
            ),
        },
    }
    try:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            service,
            payload,
            blocking=False,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Cannot send Calling Messenger Hub notification: %s", err)


def _entry_for_action(hass: HomeAssistant, entry_id: str) -> ConfigEntry | None:
    entry = hass.config_entries.async_get_entry(entry_id)
    if (
        entry is not None
        and entry.domain == DOMAIN
        and entry.state is ConfigEntryState.LOADED
    ):
        return entry
    return None


async def _async_clear_notification(
    hass: HomeAssistant,
    entry: ConfigEntry,
    tag: str,
) -> None:
    service = _notify_service(entry.options)
    if not tag or service is None or not hass.services.has_service(
        NOTIFY_DOMAIN, service
    ):
        return
    try:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            service,
            {"message": "clear_notification", "data": {"tag": tag}},
            blocking=False,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Cannot clear Calling Messenger Hub notification: %s", err)


async def _async_handle_action(hass: HomeAssistant, action: str) -> None:
    parts = action.split("|", 5)
    prefix = parts[0]
    entry_id = parts[1] if len(parts) > 1 else ""
    alert_id = parts[2] if len(parts) > 2 else ""
    item_id = parts[3] if len(parts) > 3 else ""
    account_id = parts[4] if len(parts) > 4 else ""
    tag = parts[5] if len(parts) > 5 else ""
    hass.bus.async_fire(
        NOTIFICATION_ACTION_EVENT,
        {
            "action": prefix,
            "entry_id": entry_id,
            "alert_id": alert_id,
            "item_id": item_id,
            "account_id": account_id,
            "tag": tag,
        },
    )
    if prefix == ACTION_OPEN:
        return
    entry = _entry_for_action(hass, entry_id)
    if entry is None:
        return
    api = entry.runtime_data.api
    try:
        if prefix == ACTION_ACK and alert_id:
            await api.async_alert_action(
                alert_id=alert_id,
                action="resolve",
                by="notification",
            )
        elif prefix == ACTION_HANGUP and item_id:
            await api.async_hangup(
                call_id=item_id,
                account=account_id or None,
            )
    except TelegramVoipApiError as err:
        _LOGGER.warning("Calling Messenger Hub notification action failed: %s", err)
        return
    await _async_clear_notification(hass, entry, tag)


@callback
def _handle_notification_action(hass: HomeAssistant, event: Event[Any]) -> None:
    action = str(event.data.get("action") or "")
    if not action.startswith((f"{ACTION_ACK}|", f"{ACTION_HANGUP}|", ACTION_OPEN)):
        return
    hass.async_create_task(_async_handle_action(hass, action))


@callback
def async_register_notification_actions(hass: HomeAssistant) -> None:
    if DATA_NOTIFICATION_ACTIONS in hass.data:
        return

    @callback
    def _handle(event: Event[Any]) -> None:
        _handle_notification_action(hass, event)

    hass.data[DATA_NOTIFICATION_ACTIONS] = hass.bus.async_listen(
        MOBILE_APP_ACTION_EVENT,
        _handle,
    )


@callback
def async_unregister_notification_actions(hass: HomeAssistant) -> None:
    unsubscribe = hass.data.pop(DATA_NOTIFICATION_ACTIONS, None)
    if unsubscribe is not None:
        unsubscribe()
