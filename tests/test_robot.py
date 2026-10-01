import json

from conftest import wait_for


def state(client):
    return client.app.state.telemetry.state


def test_sse_events_carry_timestamp():
    from conftest import make_config
    from pudubot2_sim.telemetry import TelemetryBroker

    broker = TelemetryBroker(make_config())
    for event in broker._seed_events():
        envelope = json.loads(event)
        assert set(envelope) == {"type", "data", "timestamp"}
    assert state_types(broker) >= {"pose", "BatteryLevel", "Estop"}


def state_types(broker):
    return {json.loads(e)["type"] for e in broker._seed_events()}


def test_navigation_arrives_and_drains_battery(client):
    assert client.post("/navigation/start", json={"waypointId": "A"}).json() == {"started": True}
    assert client.get("/navigation/status").json() == {"status": "MOVING"}
    wait_for(lambda: client.get("/navigation/status").json()["status"] == "ARRIVED")
    assert client.get("/pose").json() == {"x": 3.0, "y": 0.0, "theta": 1.0}
    assert client.get("/battery/level").json() == {"battery": 47}  # 3 m at 1%/m


def test_navigation_unknown_waypoint(client):
    assert client.post("/navigation/start", json={"waypointId": "nope"}).status_code == 400


def test_navigation_fail_injection(client):
    assert client.post("/sim/navigation/fail", json={}).status_code == 409
    client.post("/navigation/start", json={"waypointId": "A"})
    assert client.post("/sim/navigation/fail", json={"status": "STUCK"}).status_code == 200
    assert client.get("/navigation/status").json() == {"status": "STUCK"}
    assert not client.app.state.navigation.moving


def test_estop_pauses_navigation(make_client):
    client = make_client(navigation_speed_m_per_s=1.0)
    client.post("/sim/estop", json={"estop": True})
    client.post("/navigation/start", json={"waypointId": "A"})
    wait_for(lambda: client.get("/navigation/status").json()["status"] == "PAUSE")
    assert client.get("/pose").json()["x"] == 0.0
    client.post("/sim/estop", json={"estop": False})
    wait_for(lambda: client.get("/navigation/status").json()["status"] in ("MOVING", "APPROACHING"))
    client.post("/navigation/stop")


def test_charge_drives_to_dock_then_charges(client):
    client.post("/navigation/start", json={"waypointId": "A"})
    wait_for(lambda: client.get("/pose").json()["x"] == 3.0)
    assert client.get("/charge").json() == {"charging": True}
    wait_for(lambda: client.get("/battery/charging").json() == {"battery": True})
    assert client.get("/pose").json()["x"] == 0.0
    wait_for(lambda: client.get("/battery/level").json() == {"battery": 100})


def test_leaving_dock_stops_charging(client):
    client.get("/charge")
    wait_for(lambda: state(client).charging)
    client.post("/navigation/start", json={"waypointId": "A"})
    assert state(client).charging is False


def test_charge_without_charger_is_noop(client):
    client.post("/map/switch", json={"mapName": "L9"})
    wait_for(lambda: client.get("/map/current").json() == {"map": "L9"})
    assert client.get("/charge").json() == {"charging": True}
    assert state(client).charging is False


def test_user_acknowledgement_manual(client):
    assert client.post("/user_interaction/command", json={}).status_code == 400
    assert client.post("/user_interaction/command", json={"user_acknowledgment": True}).json() == {"received": True}
    assert state(client).awaiting_user_input is True
    assert client.post("/sim/acknowledge").json() == {"acknowledged": True}
    assert state(client).awaiting_user_input is False
    assert client.post("/sim/acknowledge").json() == {"acknowledged": False}


def test_user_acknowledgement_auto(make_client):
    client = make_client(auto_acknowledge_seconds=0.1)
    client.post("/user_interaction/command", json={"user_acknowledgment": True})
    assert state(client).awaiting_user_input is True
    wait_for(lambda: state(client).awaiting_user_input is False)


def test_delivery_items_and_state(client):
    assert client.post("/set_delivery_items", json={"delivery_items": ["a", "b"]}).json() == {"received": True}
    assert client.app.state.interaction.delivery_items == ["a", "b"]
    client.post("/set_delivery_items", json={"delivery_items": "Delivery"})
    assert client.app.state.interaction.delivery_items == ["Delivery"]
    assert client.post("/set_delivery_items", json={}).status_code == 400
    assert client.get("/user_interaction/state").json() == {"state": "not_implemented"}
    assert client.post("/set_delivery_status", json={"delivery_status": "x"}).status_code == 404


def test_localization_by_pose_and_waypoint(client):
    assert client.get("/localization/status").json() == {"localized": True}
    assert client.post("/localization/by_pose", json={"x": 2, "y": 3, "theta": 0.5}).json() == {"relocating": True}
    assert client.get("/localization/status").json() == {"localized": False}
    wait_for(lambda: client.get("/localization/status").json()["localized"])
    assert client.get("/pose").json() == {"x": 2.0, "y": 3.0, "theta": 0.5}

    client.post("/localization/by_waypoint_name", json={"waypoint": "A"})
    wait_for(lambda: client.get("/pose").json()["x"] == 3.0)
    assert client.post("/localization/by_waypoint_name", json={"waypoint": "zzz"}).json() == {"relocating": True}
    assert client.get("/localization/status").json() == {"localized": True}
    assert client.post("/localization/by_pose").status_code == 400


def test_sim_localization_and_battery(client):
    client.post("/sim/localization", json={"localized": False})
    assert client.get("/localization/status").json() == {"localized": False}
    assert client.post("/sim/battery", json={"level": 12}).json() == {"battery": 12}
    assert state(client).battery_level == 12
    assert client.post("/sim/battery", json={"level": "x"}).status_code == 400
    assert client.post("/sim/estop", json={"estop": True}).json() == {"estop": True}
    assert state(client).estop is True


def test_map_switch_failure_injection(client):
    client.post("/sim/map_switch_failure", json={"fail": True})
    client.post("/map/switch", json={"mapName": "L9"})
    import time
    time.sleep(0.4)
    assert client.get("/map/current").json() == {"map": "L8"}
    # one-shot: the next switch succeeds
    client.post("/map/switch", json={"mapName": "L9"})
    wait_for(lambda: client.get("/map/current").json() == {"map": "L9"})


def test_audio_stubs(client):
    assert client.get("/audio/play").json() == {"Audio Triggered": True}
    assert client.get("/audio/stop").json() == {"Audio Stopped": True}


def test_sim_api_can_be_disabled(make_client):
    client = make_client(enable_sim_api=False)
    assert client.post("/sim/estop", json={"estop": True}).status_code == 404
