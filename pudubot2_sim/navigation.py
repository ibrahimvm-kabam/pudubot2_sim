"""Simulates the robot moving between waypoints."""

from __future__ import annotations

import asyncio
import math

from pudubot2_sim.config import Pose
from pudubot2_sim.mapping import MapConfig, Waypoint
from pudubot2_sim.telemetry import TelemetryBroker

# How often the simulated pose is updated and published while moving.
TICK_SECONDS = 0.2


class NavigationController:
    """Moves the simulated pose toward a waypoint at a configured speed."""

    def __init__(
        self,
        telemetry: TelemetryBroker,
        maps: dict[str, MapConfig],
        speed_m_per_s: float,
    ) -> None:
        self._telemetry = telemetry
        self._maps = maps
        self._speed_m_per_s = speed_m_per_s
        self._task: asyncio.Task | None = None

    def start(self, waypoint_id: str) -> bool:
        """Starts moving toward the waypoint. Returns False if it's unknown on the active map."""
        current_map = self._maps[self._telemetry.state.active_map]
        target = current_map.find_waypoint(waypoint_id)
        if target is None:
            return False
        self.stop()
        self._task = asyncio.create_task(self._navigate_to(target))
        return True

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _navigate_to(self, target: Waypoint) -> None:
        self._telemetry.set_navigation_status("MOVING")
        start = self._telemetry.state.pose
        distance = math.hypot(target.x - start.x, target.y - start.y)
        # Shortest signed angular delta, so the simulated turn doesn't go the
        # long way around when start/target thetas straddle +-pi.
        delta_theta = math.atan2(
            math.sin(target.theta - start.theta), math.cos(target.theta - start.theta)
        )
        # Duration is based on distance only, so a pure rotation (distance 0,
        # theta changed) turns instantly rather than over intermediate ticks.
        duration = distance / self._speed_m_per_s if self._speed_m_per_s > 0 else 0.0

        elapsed = 0.0
        while elapsed + TICK_SECONDS < duration:
            await asyncio.sleep(TICK_SECONDS)
            elapsed += TICK_SECONDS
            fraction = elapsed / duration
            self._telemetry.set_pose(
                Pose(
                    x=start.x + (target.x - start.x) * fraction,
                    y=start.y + (target.y - start.y) * fraction,
                    theta=start.theta + delta_theta * fraction,
                )
            )

        if duration > 0:
            await asyncio.sleep(duration - elapsed)
        self._telemetry.set_pose(Pose(x=target.x, y=target.y, theta=target.theta))
        self._telemetry.set_navigation_status("ARRIVED")
        self._task = None
