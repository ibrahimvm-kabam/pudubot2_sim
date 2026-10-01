import time

import pytest
from fastapi.testclient import TestClient

from pudubot2_sim import app as app_module
from pudubot2_sim.app import create_app
from pudubot2_sim.config import Config, Pose

MAPS = {
    "L8": {
        "charger_waypoint": "Dock",
        "waypoints": [
            {"id": "Dock", "x": 0.0, "y": 0.0, "theta": 0.0},
            {"id": "A", "x": 3.0, "y": 0.0, "theta": 1.0},
        ],
    },
    "L9": {"waypoints": [{"id": "B", "x": 1.0, "y": 1.0, "theta": 0.0}]},
}


def make_config(**overrides) -> Config:
    values = dict(
        robot_name="Test",
        port=0,
        initial_map="L8",
        initial_pose=Pose(0.0, 0.0, 0.0),
        initial_battery=50,
        navigation_speed_m_per_s=30.0,
        maps=MAPS,
        battery_drain_percent_per_meter=1.0,
        charge_percent_per_second=100.0,
        docking_seconds=0.1,
        localization_delay_seconds=0.1,
        auto_acknowledge_seconds=None,
    )
    values.update(overrides)
    return Config(**values)


@pytest.fixture(autouse=True)
def fast_map_switch(monkeypatch):
    monkeypatch.setattr(app_module, "MAP_SWITCH_DELAY_SECONDS", 0.1)


@pytest.fixture
def make_client():
    clients = []

    def _make(**overrides):
        client = TestClient(create_app(make_config(**overrides)))
        client.__enter__()
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client):
    return make_client()


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met in time")
