"""In-memory robot state, and pub/sub for streaming its changes over SSE.

Event type names match pudubot2_adapter's `/events` contract exactly, since
fleet_adapter_pudu parses incoming SSE data as `{"type": <name>, "data": ...}`
and switches on `type`.
"""

from __future__ import annotations

import asyncio
import json
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
        message = json.dumps({"type": event_type, "data": data})
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

    def _seed_events(self) -> list[str]:
        """The current value of every field, sent to a subscriber on connect."""
        state = self.state
        return [
            json.dumps({"type": POSE, "data": asdict(state.pose)}),
            json.dumps({"type": NAVIGATION_STATUS, "data": state.navigation_status}),
            json.dumps({"type": LOCALIZATION_STATUS, "data": state.localized}),
            json.dumps({"type": ACTIVE_MAP, "data": state.active_map}),
            json.dumps({"type": USER_ACKNOWLEDGEMENT_STATUS, "data": state.awaiting_user_input}),
            json.dumps({"type": BATTERY_LEVEL, "data": state.battery_level}),
            json.dumps({"type": CHARGING_STATUS, "data": state.charging}),
            json.dumps({"type": ESTOP, "data": state.estop}),
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
