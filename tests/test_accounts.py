from __future__ import annotations

from custom_components.calling_messenger_hub.accounts import AccountEntityRegistry


class FakeEntity:
    def __init__(self, key):
        self.key = key
        self.removed = False

    def async_remove(self):
        self.removed = True


class FakeCoordinator:
    def __init__(self, accounts):
        self.data = {"accounts": accounts}
        self.listeners = []

    def async_add_listener(self, listener):
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)

    def set_accounts(self, accounts):
        self.data = {"accounts": accounts}
        for listener in list(self.listeners):
            listener()


def test_account_registry_adds_and_removes_entities():
    added = []
    coordinator = FakeCoordinator([{"id": "a"}])
    registry = AccountEntityRegistry(
        coordinator,
        added.extend,
        lambda account: [(account["id"], FakeEntity(account["id"]))],
    )
    first = added[0]

    coordinator.set_accounts([{"id": "a"}, {"id": "b"}])
    assert [item.key for item in added] == ["a", "b"]
    assert first.removed is False

    coordinator.set_accounts([{"id": "b"}])
    assert first.removed is True

    registry.async_stop()
    assert coordinator.listeners == []
