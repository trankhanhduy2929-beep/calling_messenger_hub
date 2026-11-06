from __future__ import annotations

import logging
import re
import time
from datetime import time as dt_time
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .api import TelegramVoipApiError
from .const import (
    CONF_NOTIFY_ACCOUNTS,
    CONF_NOTIFY_COOLDOWN,
    CONF_NOTIFY_CRITICAL_SERVICES,
    CONF_NOTIFY_EVENTS,
    CONF_NOTIFY_QUIET_END,
    CONF_NOTIFY_QUIET_START,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_SERVICES,
    CONF_NOTIFY_SEVERITIES,
    CONF_NOTIFY_URL,
    DEFAULT_NOTIFY_COOLDOWN,
    DEFAULT_NOTIFY_EVENTS,
    DEFAULT_NOTIFY_SEVERITIES,
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
ACTION_OPEN_CHAT = "CMH_OPEN_CHAT"
_PHONE_RE = re.compile(r"^\+?\d{5,15}$")
_TELEGRAM_ID_RE = re.compile(r"^\d{1,20}$")
_TELEGRAM_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,31}$")
_ZALO_ID_RE = re.compile(r"^\d{5,20}$")
DATA_NOTIFICATION_ACTIONS = f"{DOMAIN}_notification_actions"
DATA_NOTIFICATION_COOLDOWN = f"{DOMAIN}_notification_cooldown"

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


def _split_values(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        raw = [str(item) for item in value]
    else:
        raw = re.split(r"[,;\n]+", str(value or ""))
    return [item.strip() for item in raw if item.strip()]

def _parse_services(value: Any) -> list[str]:
    services: list[str] = []
    for item in _split_values(value):
        service = item.removeprefix(f"{NOTIFY_DOMAIN}.")
        if service and service not in services:
            services.append(service)
    return services

def _notify_services(options: dict[str, Any]) -> list[str]:
    services = _parse_services(options.get(CONF_NOTIFY_SERVICES))
    if not services:
        services = _parse_services(options.get(CONF_NOTIFY_SERVICE))
    return services

def _critical_services(options: dict[str, Any]) -> list[str]:
    return _parse_services(options.get(CONF_NOTIFY_CRITICAL_SERVICES))

def _notification_services(
    options: dict[str, Any],
    event: dict[str, Any],
) -> list[str]:
    services = _notify_services(options)
    if _event_severity(event) == "critical":
        services = _critical_services(options) or services
    return services

def _all_notify_services(options: dict[str, Any]) -> list[str]:
    services = list(_notify_services(options))
    for service in _critical_services(options):
        if service not in services:
            services.append(service)
    return services

def _event_severity(event: dict[str, Any]) -> str:
    severity = str(event.get("severity") or "info").strip().lower()
    return severity if severity in _SEVERITIES else "info"

def _parse_clock(value: Any) -> dt_time | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt_time.fromisoformat(text)
    except ValueError:
        return None

def _in_quiet_hours(
    options: dict[str, Any],
    now: dt_time | None = None,
) -> bool:
    start = _parse_clock(options.get(CONF_NOTIFY_QUIET_START))
    end = _parse_clock(options.get(CONF_NOTIFY_QUIET_END))
    if start is None or end is None or start == end:
        return False
    current = now or dt_util.now().time()
    if start < end:
        return start <= current < end
    return current >= start or current < end

def _account_values(entry: ConfigEntry, event: dict[str, Any]) -> set[str]:
    item = _event_item(entry, event)
    account_id = str(event.get("account_id") or item.get("account_id") or "")
    service = str(event.get("service") or item.get("service") or "")
    values = {account_id, service}
    if account_id:
        for account in _coordinator_data(entry).get("accounts") or []:
            if str(account.get("id") or "") != account_id:
                continue
            values.update(
                str(account.get(key) or "")
                for key in ("id", "name", "phone", "service")
            )
            break
    return {value.strip().casefold() for value in values if value.strip()}

def _account_allowed(entry: ConfigEntry, event: dict[str, Any]) -> bool:
    selected = {
        value.casefold()
        for value in _split_values(entry.options.get(CONF_NOTIFY_ACCOUNTS))
    }
    if not selected:
        return True
    return bool(selected & _account_values(entry, event))

def _severity_allowed(entry: ConfigEntry, event: dict[str, Any]) -> bool:
    selected = set(
        _split_values(entry.options.get(CONF_NOTIFY_SEVERITIES))
        or DEFAULT_NOTIFY_SEVERITIES
    )
    return _event_severity(event) in selected

def _cooldown_seconds(options: dict[str, Any]) -> int:
    try:
        value = int(options.get(CONF_NOTIFY_COOLDOWN, DEFAULT_NOTIFY_COOLDOWN))
    except (TypeError, ValueError):
        return DEFAULT_NOTIFY_COOLDOWN
    return max(0, min(value, 3600))

def _cooldown_key(entry: ConfigEntry, event: dict[str, Any]) -> str:
    kind = str(event.get("kind") or "other")
    item = _event_item(entry, event)
    account_id = str(event.get("account_id") or item.get("account_id") or "")
    if kind in {"sms", "otp"}:
        identity = event.get("sender") or event.get("peer_id") or event.get("from")
    elif kind == "alert":
        identity = event.get("alert_id")
    elif kind in {"call", "ring"}:
        identity = event.get("call_id") or event.get("ring_id") or item.get("id")
    else:
        identity = event.get("peer_id") or event.get("sender") or event.get("id")
    return "|".join(
        part.casefold()
        for part in (entry.entry_id, kind, account_id, str(identity or ""))
    )

def _cooldown_active(
    hass: HomeAssistant,
    entry: ConfigEntry,
    event: dict[str, Any],
) -> bool:
    seconds = _cooldown_seconds(entry.options)
    if seconds <= 0:
        return False
    store: dict[str, float] = hass.data.setdefault(
        DATA_NOTIFICATION_COOLDOWN, {}
    )
    key = _cooldown_key(entry, event)
    now = time.monotonic()
    last = store.get(key)
    if last is not None and now - last < seconds:
        _LOGGER.debug("Notification suppressed by cooldown: %s", key)
        return True
    store[key] = now
    if len(store) > 2048:
        cutoff = now - 86400
        for item in [item for item, ts in store.items() if ts < cutoff]:
            store.pop(item, None)
    return False

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

def _event_service(
    entry: ConfigEntry,
    event: dict[str, Any],
    item: dict[str, Any] | None = None,
) -> str:
    item = item or _event_item(entry, event)
    account_id = str(event.get("account_id") or item.get("account_id") or "")
    return str(
        event.get("service")
        or item.get("service")
        or _account_service(entry, account_id)
    )

def _callback_target(entry: ConfigEntry, event: dict[str, Any]) -> str | None:
    kind = str(event.get("kind") or "")
    item = _event_item(entry, event)
    service = _event_service(entry, event, item)
    if kind in {"sms", "otp"}:
        if service in {"telegram", "zalo"}:
            return None
        return _phone_uri(
            event.get("sender") or event.get("peer_id") or event.get("from")
        )
    if kind not in {"call", "ring"}:
        return None
    if service != "sim":
        return None
    return _phone_uri(
        item.get("peer_id")
        or item.get("to")
        or event.get("peer_id")
        or event.get("to")
    )

def _chat_target(entry: ConfigEntry, event: dict[str, Any]) -> str | None:
    item = _event_item(entry, event)
    service = _event_service(entry, event, item)
    target = str(
        item.get("peer_id")
        or event.get("peer_id")
        or item.get("to")
        or event.get("to")
        or ""
    ).strip()
    if service == "telegram":
        name = str(
            event.get("peer_username")
            or event.get("username")
            or event.get("peer_name")
            or item.get("peer_username")
            or item.get("username")
            or item.get("peer_name")
            or ""
        ).strip()
        username = name[1:] if name.startswith("@") else ""
        if _TELEGRAM_NAME_RE.fullmatch(username):
            return f"https://t.me/{username}"
        if _TELEGRAM_ID_RE.fullmatch(target):
            return f"tg://user?id={target}"
    elif service == "zalo" and _ZALO_ID_RE.fullmatch(target):
        return f"https://zalo.me/{target}"
    return None

def should_notify(
    entry: ConfigEntry,
    event: dict[str, Any],
    now: dt_time | None = None,
) -> bool:
    if not _notification_services(entry.options, event):
        return False
    kind = str(event.get("kind") or "")
    selected = set(
        _split_values(entry.options.get(CONF_NOTIFY_EVENTS))
        or DEFAULT_NOTIFY_EVENTS
    )
    if kind not in selected:
        return False
    if kind == "alert":
        if not event.get("alert_id") or event.get("status"):
            return False
    elif kind in {"sms", "otp"} and not event.get("sender"):
        return False
    if not _severity_allowed(entry, event):
        return False
    if not _account_allowed(entry, event):
        return False
    return _event_severity(event) == "critical" or not _in_quiet_hours(
        entry.options, now
    )


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
    chat = _chat_target(entry, event)
    if chat:
        actions.append(
            {
                "action": ACTION_OPEN_CHAT,
                "title": "Mở chat",
                "uri": chat,
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
    services = [
        service
        for service in _notification_services(entry.options, event)
        if hass.services.has_service(NOTIFY_DOMAIN, service)
    ]
    if not services:
        _LOGGER.debug(
            "Notification services are not available: %s",
            ", ".join(_notification_services(entry.options, event)),
        )
        return
    if _cooldown_active(hass, entry, event):
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
    for service in services:
        try:
            await hass.services.async_call(
                NOTIFY_DOMAIN,
                service,
                payload,
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Cannot send Calling Messenger Hub notification via notify.%s: %s",
                service,
                err,
            )


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
    if not tag:
        return
    for service in _all_notify_services(entry.options):
        if not hass.services.has_service(NOTIFY_DOMAIN, service):
            continue
        try:
            await hass.services.async_call(
                NOTIFY_DOMAIN,
                service,
                {"message": "clear_notification", "data": {"tag": tag}},
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug(
                "Cannot clear Calling Messenger Hub notification via notify.%s: %s",
                service,
                err,
            )


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
    if action.split("|", 1)[0] not in {ACTION_ACK, ACTION_HANGUP, ACTION_OPEN}:
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
