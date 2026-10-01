"""Checks the simulator against the HTTP/SSE contract of pudubot2_adapter, as consumed by fleet_adapter_pudu."""

import pytest

SLOW = {"speed": 0.5}


def test_new_subscriber_is_seeded_with_every_state_field(sim, events):
    events.wait_for("Estop")
    assert events.types() == [
        "pose", "NavigationStatus", "LocalizationStatus", "ActiveMap",
        "UserAcknowledgementStatus", "BatteryLevel", "ChargingStatus", "Estop",
    ]  # fmt: skip
    assert events.wait_for("BatteryLevel")["data"] == 80


def test_navigation_reports_moving_then_arrived_at_waypoint(sim, events):
    assert sim.post("/navigation/start", json={"waypointId": "Reception"}).json() == {"started": True}
    events.wait_for("NavigationStatus", "MOVING")
    events.wait_for("NavigationStatus", "ARRIVED")
    assert sim.get("/pose").json() == {"x": 4.5, "y": 12.9, "theta": -2.1}
    assert sim.get("/navigation/status").json() == {"status": "ARRIVED"}


def test_navigation_to_unknown_waypoint_is_rejected(sim):
    assert sim.post("/navigation/start", json={"waypointId": "Nowhere"}).status_code == 400


@pytest.mark.parametrize("sim", [SLOW], indirect=True)
def test_navigation_stop_halts_movement(sim, events):
    sim.post("/navigation/start", json={"waypointId": "Charging Dock"})
    events.wait_for("NavigationStatus", "MOVING")
    sim.post("/navigation/stop")
    assert sim.get("/navigation/status").json() == {"status": "MOVING"}
    pose = sim.get("/pose").json()
    assert pose != {"x": -6.0, "y": 16.0, "theta": -0.5}


def test_map_switch_publishes_result_then_active_map(sim, events):
    assert sim.post("/map/switch", json={"mapName": "L9"}).json() == {"switching": True}
    events.wait_for("SwitchMapResult", True)
    events.wait_for("ActiveMap", "L9")
    assert sim.get("/map/current").json() == {"map": "L9"}
    assert [w["id"] for w in sim.get("/map/waypoints").json()["waypoints"]] == ["L9_holding"]
