"""User interaction, delivery and audio endpoints."""


def test_user_acknowledgement_command_is_published(sim, events):
    assert sim.post("/user_interaction/command", json={"user_acknowledgment": True}).json() == {"received": True}
    events.wait_for("UserAcknowledgementStatus", True)


def test_user_interaction_command_requires_acknowledgement_field(sim):
    assert sim.post("/user_interaction/command", json={}).status_code == 422


def test_delivery_items_accepts_a_list_of_strings(sim):
    assert sim.post("/set_delivery_items", json={"delivery_items": ["Towels", "Water"]}).json() == {"received": True}


def test_delivery_items_must_be_a_list_like_the_real_robot_requires(sim):
    assert sim.post("/set_delivery_items", json={"delivery_items": "Towels"}).status_code == 422


def test_audio_and_user_interaction_state_stubs(sim):
    assert sim.get("/audio/play").json() == {"Audio Triggered": True}
    assert sim.get("/audio/stop").json() == {"Audio Stopped": True}
    assert sim.get("/user_interaction/state").json() == {"state": "not_implemented"}
