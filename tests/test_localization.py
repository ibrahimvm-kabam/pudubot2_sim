"""Relocalization behaviour."""



def test_localization_by_pose_reports_unlocalized_then_localized(sim, events):
    assert sim.get("/localization/status").json() == {"localized": True}
    assert sim.post("/localization/by_pose", json={"x": 1.0, "y": 2.0, "theta": 0.3}).json() == {"relocating": True}
    events.wait_for("LocalizationStatus", False)
    assert sim.get("/localization/status").json() == {"localized": False}
    # Seeded LocalizationStatus is already True, so wait on the pose that precedes the final update.
    events.wait_for("pose", {"x": 1.0, "y": 2.0, "theta": 0.3})
    assert sim.get("/localization/status").json() == {"localized": True}


def test_localization_by_waypoint_name_moves_pose_to_waypoint(sim, events):
    sim.post("/localization/by_waypoint_name", json={"waypoint": "Reception"})
    events.wait_for("pose", {"x": 4.5, "y": 12.9, "theta": -2.1})


def test_localization_by_unknown_waypoint_is_rejected(sim):
    assert sim.post("/localization/by_waypoint_name", json={"waypoint": "Nowhere"}).status_code == 400
