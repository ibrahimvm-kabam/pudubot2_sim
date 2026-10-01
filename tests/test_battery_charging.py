"""Battery and charging behaviour."""


def test_charge_docks_at_charger_and_leaving_clears_charging(sim, events):
    assert sim.get("/charge").json() == {"charging": True}
    events.wait_for("ChargingStatus", True)
    assert sim.get("/pose").json() == {"x": -6.0, "y": 16.0, "theta": -0.5}
    assert sim.get("/battery/charging").json() == {"battery": True}

    sim.post("/navigation/start", json={"waypointId": "Reception"})
    events.wait_for("ChargingStatus", False)


def test_charge_without_charger_on_active_map_is_rejected(sim, events):
    sim.post("/map/switch", json={"mapName": "L9"})
    events.wait_for("ActiveMap", "L9")
    assert sim.get("/charge").status_code == 400


def test_battery_level_is_reported_as_whole_percentage(sim):
    assert sim.get("/battery/level").json() == {"battery": 80}


def test_battery_rises_while_charging(sim, events):
    sim.get("/charge")
    events.wait_for("BatteryLevel", 100)
