"""Test controls under /sim."""

import pytest

SLOW = {"speed": 0.5}



def test_forced_battery_level_is_reported_as_whole_percentage(sim, events):
    assert sim.get("/battery/level").json() == {"battery": 80}
    sim.post("/sim/battery", json={"level": 42.7})
    events.wait_for("BatteryLevel", 43)
    assert sim.get("/battery/level").json() == {"battery": 43}


def test_battery_level_out_of_range_is_rejected(sim):
    assert sim.post("/sim/battery", json={"level": 101}).status_code == 422


def test_user_acknowledgement_tap_clears_awaiting_state(sim, events):
    assert sim.post("/user_interaction/command", json={"user_acknowledgment": True}).json() == {"received": True}
    events.wait_for("UserAcknowledgementStatus", True)

    assert sim.post("/sim/user_acknowledgement").json() == {"acknowledged": True}
    events.wait_for("UserAcknowledgementStatus", False)


def test_user_acknowledgement_while_not_awaiting_is_rejected(sim):
    assert sim.post("/sim/user_acknowledgement").status_code == 409


def test_delivery_items_are_visible_in_state(sim):
    assert sim.post("/set_delivery_items", json={"delivery_items": ["Towels", "Water"]}).json() == {"received": True}
    assert sim.get("/sim/state").json()["delivery_items"] == ["Towels", "Water"]


@pytest.mark.parametrize("sim", [SLOW], indirect=True)
def test_estop_halts_navigation_and_is_published(sim, events):
    sim.post("/navigation/start", json={"waypointId": "Charging Dock"})
    events.wait_for("NavigationStatus", "MOVING")
    sim.post("/sim/estop", json={"estop": True})
    events.wait_for("Estop", True)
    pose = sim.get("/pose").json()
    assert sim.get("/pose").json() == pose


@pytest.mark.parametrize("sim", [SLOW], indirect=True)
def test_forced_stuck_status_halts_navigation(sim, events):
    sim.post("/navigation/start", json={"waypointId": "Charging Dock"})
    events.wait_for("NavigationStatus", "MOVING")
    sim.post("/sim/navigation_status", json={"status": "STUCK"})
    events.wait_for("NavigationStatus", "STUCK")
    assert sim.get("/navigation/status").json() == {"status": "STUCK"}


def test_forced_navigation_status_must_be_a_known_name(sim):
    assert sim.post("/sim/navigation_status", json={"status": "stuck"}).status_code == 422
