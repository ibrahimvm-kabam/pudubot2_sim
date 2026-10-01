"""In-memory robot state, and pub/sub for streaming its changes over SSE.

Event type names match pudubot2_adapter's `/events` contract exactly, since
fleet_adapter_pudu parses incoming SSE data as `{"type": <name>, "data": ...}`
and switches on `type`.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass

from pudubot2_sim.config import Config, Pose

POSE = "pose"
NAVIGATION_STATUS = "NavigationStatus"
LOCALIZATION_STATUS = "LocalizationStatus"
ACTIVE_MAP = "ActiveMap"
USER_ACKNOWLEDGEMENT_STATUS = "UserAcknowledgementStatus"
BATTERY_LEVEL = "BatteryLevel"
CHARGING_STATUS = "ChargingStatus"
ESTOP = "Estop"
SWITCH_MAP_RESULT = "SwitchMapResult"


def _envelope(event_type: str, data: object) -> str:
    """The `{type, data, timestamp}` wrapper pudubot2_adapter puts on every SSE event."""
    return json.dumps(
        {"type": event_type, "data": data, "timestamp": int(time.time() * 1000)}
    )


@dataclass
class RobotState:
    pose: Pose
    battery_level: float
    charging: bool
    localized: bool
    active_map: str
    navigation_status: str
    awaiting_user_input: bool
    estop: bool

    @classmethod
    def from_config(cls, config: Config) -> RobotState:
        return cls(
            pose=config.initial_pose,
            battery_level=config.initial_battery,
            charging=False,
            localized=True,
            active_map=config.initial_map,
            navigation_status="UNKNOWN",
            awaiting_user_input=False,
            estop=False,
        )


class TelemetryBroker:
    """Holds the robot's live state and publishes changes to SSE subscribers."""

    def __init__(self, config: Config) -> None:
        self.state = RobotState.from_config(config)
        self._subscribers: list[asyncio.Queue[str]] = []

    def _publish(self, event_type: str, data: object) -> None:
        message = _envelope(event_type, data)
        for queue in self._subscribers:
            queue.put_nowait(message)

    def set_pose(self, pose: Pose) -> None:
        self.state.pose = pose
        self._publish(POSE, asdict(pose))

    def set_battery_level(self, level: float) -> None:
        self.state.battery_level = level
        self._publish(BATTERY_LEVEL, level)

    def set_charging(self, charging: bool) -> None:
        self.state.charging = charging
        self._publish(CHARGING_STATUS, charging)

    def set_localized(self, localized: bool) -> None:
        self.state.localized = localized
        self._publish(LOCALIZATION_STATUS, localized)

    def set_active_map(self, map_name: str) -> None:
        self.state.active_map = map_name
        self._publish(ACTIVE_MAP, map_name)

    def set_navigation_status(self, status: str) -> None:
        self.state.navigation_status = status
        self._publish(NAVIGATION_STATUS, status)

    def set_awaiting_user_input(self, waiting: bool) -> None:
        self.state.awaiting_user_input = waiting
        self._publish(USER_ACKNOWLEDGEMENT_STATUS, waiting)

    def set_estop(self, estop: bool) -> None:
        self.state.estop = estop
        self._publish(ESTOP, estop)

    def publish_switch_map_result(self, success: bool) -> None:
        """Signals the outcome of a map switch.

        Not part of `RobotState` and never seeded to a new subscriber - it's
        a one-off result for whichever switch just completed, not a
        steady-state field.
        """
        self._publish(SWITCH_MAP_RESULT, success)

    def _seed_events(self) -> list[str]:
        """The current value of every field, sent to a subscriber on connect."""
        state = self.state
        return [
            _envelope(POSE, asdict(state.pose)),
            _envelope(NAVIGATION_STATUS, state.navigation_status),
            _envelope(LOCALIZATION_STATUS, state.localized),
            _envelope(ACTIVE_MAP, state.active_map),
            _envelope(USER_ACKNOWLEDGEMENT_STATUS, state.awaiting_user_input),
            _envelope(BATTERY_LEVEL, state.battery_level),
            _envelope(CHARGING_STATUS, state.charging),
            _envelope(ESTOP, state.estop),
        ]

    async def subscribe(self):
        """Yields the current state, then every subsequent update, as SSE data strings."""
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            for event in self._seed_events():
                yield event
            while True:
                yield await queue.get()
        finally:
            self._subscribers.remove(queue)
