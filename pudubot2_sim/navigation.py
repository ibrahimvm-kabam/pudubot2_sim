"""Simulates the robot moving between waypoints."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable

from pudubot2_sim.battery import BatteryController
from pudubot2_sim.config import Pose
from pudubot2_sim.mapping import MapConfig, Waypoint
from pudubot2_sim.telemetry import TelemetryBroker

# How often the simulated pose is updated and published while moving.
TICK_SECONDS = 0.2

# Remaining distance below which the robot reports APPROACHING, like the real one.
APPROACH_DISTANCE_M = 1.0

# Statuses pudubot2_adapter can report for a failed navigation.
FAILURE_STATUSES = ("STUCK", "FAIL_ESCAPE")


class NavigationController:
    """Moves the simulated pose toward a waypoint at a configured speed."""

    def __init__(
        self,
        telemetry: TelemetryBroker,
        maps: dict[str, MapConfig],
        speed_m_per_s: float,
        battery: BatteryController,
    ) -> None:
        self._telemetry = telemetry
        self._maps = maps
        self._speed_m_per_s = speed_m_per_s
        self._battery = battery
        self._task: asyncio.Task | None = None

    @property
    def moving(self) -> bool:
        return self._task is not None

    def start(self, waypoint_id: str) -> bool:
        """Starts moving toward the waypoint. Returns False if it's unknown on the active map."""
        target = self._active_map().find_waypoint(waypoint_id)
        if target is None:
            return False
        self._start_to(target)
        return True

    def charge(self) -> None:
        """Drives to the active map's charger waypoint, then docks.

        With no charger configured this is a no-op, like the real robot (which
        still answers the request successfully).
        """
        charger = self._active_map().charger_waypoint()
        if charger is not None:
            self._start_to(charger, on_arrived=self._battery.dock)

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    def fail(self, status: str) -> bool:
        """Aborts the in-flight navigation with a failure status. False if not moving."""
        if self._task is None:
            return False
        self.stop()
        self._telemetry.set_navigation_status(status)
        return True

    def _active_map(self) -> MapConfig:
        return self._maps[self._telemetry.state.active_map]

    def _start_to(
        self, target: Waypoint, on_arrived: Callable[[], None] | None = None
    ) -> None:
        self.stop()
        # Leaving the dock (or a pending dock) ends charging.
        self._battery.undock()
        self._telemetry.set_navigation_status("MOVING")
        self._task = asyncio.create_task(self._navigate_to(target, on_arrived))

    async def _navigate_to(
        self, target: Waypoint, on_arrived: Callable[[], None] | None
    ) -> None:
        start = self._telemetry.state.pose
        distance = math.hypot(target.x - start.x, target.y - start.y)
        # Shortest signed angular delta, so the simulated turn doesn't go the
        # long way around when start/target thetas straddle +-pi.
        delta_theta = math.atan2(
            math.sin(target.theta - start.theta), math.cos(target.theta - start.theta)
        )

        # A pure rotation (distance 0), or a zero speed, jumps straight to the
        # target rather than turning over intermediate ticks.
        traveled = 0.0
        paused = False
        approaching = False
        while self._speed_m_per_s > 0 and traveled < distance:
            await asyncio.sleep(TICK_SECONDS)
            if self._telemetry.state.estop:
                if not paused:
                    paused = True
                    self._telemetry.set_navigation_status("PAUSE")
                continue
            if paused:
                paused = False
                self._telemetry.set_navigation_status("RESUME")
                self._telemetry.set_navigation_status("MOVING")

            step = min(self._speed_m_per_s * TICK_SECONDS, distance - traveled)
            traveled += step
            self._battery.drain(step)
            if traveled >= distance:
                break  # the final pose is published once, exactly, below
            fraction = traveled / distance
            self._telemetry.set_pose(
                Pose(
                    x=start.x + (target.x - start.x) * fraction,
                    y=start.y + (target.y - start.y) * fraction,
                    theta=start.theta + delta_theta * fraction,
                )
            )
            if not approaching and distance - traveled < APPROACH_DISTANCE_M:
                approaching = True
                self._telemetry.set_navigation_status("APPROACHING")

        self._telemetry.set_pose(Pose(x=target.x, y=target.y, theta=target.theta))
        self._telemetry.set_navigation_status("ARRIVED")
        self._task = None
        if on_arrived is not None:
            on_arrived()
