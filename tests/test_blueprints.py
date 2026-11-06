from __future__ import annotations

from pathlib import Path

import yaml
from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.models import Blueprint

BLUEPRINT_DIR = (
    Path(__file__).parent.parent
    / "blueprints"
    / "automation"
    / "calling_messenger_hub"
)

class InputLoader(yaml.SafeLoader):
    pass

def _construct_input(loader, node):
    return loader.construct_scalar(node)

InputLoader.add_constructor("!input", _construct_input)

def _load(name):
    path = BLUEPRINT_DIR / name
    data = yaml.load(path.read_text(), Loader=InputLoader)
    Blueprint(
        data,
        path=str(path),
        expected_domain="automation",
        schema=AUTOMATION_BLUEPRINT_SCHEMA,
    )
    return data

def test_event_entity_blueprint():
    data = _load("event_actions.yaml")
    blueprint = data["blueprint"]
    assert blueprint["domain"] == "automation"
    assert set(blueprint["input"]) == {"event_entity", "event_type", "actions"}
    assert data["triggers"][0]["platform"] == "state"
    assert data["conditions"][0]["condition"] == "template"
    assert data["actions"] == "actions"
    assert data["mode"] == "queued"

def test_device_trigger_blueprint():
    data = _load("device_trigger_actions.yaml")
    blueprint = data["blueprint"]
    assert blueprint["domain"] == "automation"
    assert set(blueprint["input"]) == {"device", "event_type", "actions"}
    trigger = data["triggers"][0]
    assert trigger["platform"] == "device"
    assert trigger["domain"] == "calling_messenger_hub"
    assert trigger["type"] == "event_type"
    assert data["actions"] == "actions"
    assert data["mode"] == "queued"
