"""Simulates the delivery tablet: waiting for a user to tap "Done"."""

from __future__ import annotations

import asyncio

from pudubot2_sim.telemetry import TelemetryBroker


class UserInteractionController:
    def __init__(
        self, telemetry: TelemetryBroker, auto_acknowledge_seconds: float | None
    ) -> None:
        self._telemetry = telemetry
        self._auto_acknowledge_seconds = auto_acknowledge_seconds
        self._task: asyncio.Task | None = None
        self.delivery_items: list[str] = []

    def set_waiting(self, waiting: bool) -> None:
        """Handles the adapter's `user_acknowledgment` command."""
        self._cancel_auto_acknowledge()
        self._telemetry.set_awaiting_user_input(waiting)
        if waiting and self._auto_acknowledge_seconds is not None:
            self._task = asyncio.create_task(self._auto_acknowledge())

    def acknowledge(self) -> bool:
        """Simulates the user tapping Done. False if nothing was waiting."""
        if not self._telemetry.state.awaiting_user_input:
            return False
        self.set_waiting(False)
        return True

    def _cancel_auto_acknowledge(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _auto_acknowledge(self) -> None:
        await asyncio.sleep(self._auto_acknowledge_seconds)
        self._task = None
        self._telemetry.set_awaiting_user_input(False)
