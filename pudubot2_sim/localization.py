"""Simulates (re)localization requests."""

from __future__ import annotations

import asyncio

from pudubot2_sim.config import Pose
from pudubot2_sim.telemetry import TelemetryBroker


class LocalizationController:
    def __init__(self, telemetry: TelemetryBroker, delay_seconds: float) -> None:
        self._telemetry = telemetry
        self._delay_seconds = delay_seconds
        self._task: asyncio.Task | None = None

    def relocalize(self, pose: Pose) -> None:
        """Drops localization, then restores it at `pose` after the configured delay."""
        if self._task is not None:
            self._task.cancel()
        self._telemetry.set_localized(False)
        self._task = asyncio.create_task(self._finish(pose))

    def set_localized(self, localized: bool) -> None:
        """Forces the status directly (fault injection), cancelling any relocalization."""
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._telemetry.set_localized(localized)

    async def _finish(self, pose: Pose) -> None:
        await asyncio.sleep(self._delay_seconds)
        self._task = None
        self._telemetry.set_pose(pose)
        self._telemetry.set_localized(True)
