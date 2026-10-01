"""Runs the simulator on a real local port, so tests exercise the same HTTP/SSE stack as the fleet adapter."""

import json
import threading
import time

import httpx
import pytest
import uvicorn

from pudubot2_sim import app as app_module
from pudubot2_sim.app import create_app
from pudubot2_sim.config import Config, Pose

CONFIG = Config(
    robot_name="TestBot",
    port=0,
    initial_map="L8",
    initial_pose=Pose(x=3.0, y=9.0, theta=0.0),
    initial_battery=80,
    navigation_speed_m_per_s=100.0,
    maps={
        "L8": {
            "charger_waypoint": "Charging Dock",
            "waypoints": [
                {"id": "Charging Dock", "x": -6.0, "y": 16.0, "theta": -0.5},
                {"id": "Reception", "x": 4.5, "y": 12.9, "theta": -2.1},
            ],
        },
        "L9": {"waypoints": [{"id": "L9_holding", "x": 6.0, "y": 17.0, "theta": 0.9}]},
    },
)


class EventListener:
    """Collects the simulator's SSE events in the background, like the fleet adapter does."""

    def __init__(self, base_url: str) -> None:
        self.events: list[dict] = []
        self._response = None
        self._base_url = base_url
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _listen(self) -> None:
        try:
            with httpx.stream("GET", f"{self._base_url}/events", timeout=None) as response:
                self._response = response
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        self.events.append(json.loads(line[len("data:"):]))
        except httpx.HTTPError:
            pass  # The stream was closed by the test or the server shutting down.

    def close(self) -> None:
        if self._response is not None:
            self._response.close()

    def wait_for(self, event_type: str, data: object = None, timeout: float = 5.0) -> dict:
        """Returns the first event of this type (and data, if given) received so far or within the timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for event in list(self.events):
                if event["type"] == event_type and (data is None or event["data"] == data):
                    return event
            time.sleep(0.02)
        raise AssertionError(f"No {event_type} event with data {data!r}; got {self.events}")

    def types(self) -> list[str]:
        return [event["type"] for event in self.events]


@pytest.fixture
def sim(request, monkeypatch):
    """An httpx client pointed at a running simulator. Parametrize with {"speed": m/s} to override navigation speed."""
    monkeypatch.setattr(app_module, "MAP_SWITCH_DELAY_SECONDS", 0.1)
    speed = getattr(request, "param", {}).get("speed", CONFIG.navigation_speed_m_per_s)
    config = Config(**{**CONFIG.__dict__, "navigation_speed_m_per_s": speed})

    server = uvicorn.Server(
        uvicorn.Config(
            create_app(config),
            host="127.0.0.1",
            port=0,
            log_level="warning",
            # sse-starlette only ends open streams on a real signal, not on should_exit.
            timeout_graceful_shutdown=1,
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    base_url = "http://127.0.0.1:%d" % server.servers[0].sockets[0].getsockname()[1]

    with httpx.Client(base_url=base_url) as client:
        client.base_url_str = base_url
        yield client
    server.should_exit = True
    thread.join()


@pytest.fixture
def events(sim):
    listener = EventListener(sim.base_url_str)
    yield listener
    listener.close()
