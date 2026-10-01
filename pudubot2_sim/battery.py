"""Simulates battery drain while moving and charging while docked."""

from __future__ import annotations

import asyncio

from pudubot2_sim.telemetry import TelemetryBroker

CHARGE_TICK_SECONDS = 0.5


class BatteryController:
    def __init__(
        self,
        telemetry: TelemetryBroker,
        drain_percent_per_meter: float,
        charge_percent_per_second: float,
        docking_seconds: float,
    ) -> None:
        self._telemetry = telemetry
        self._drain_percent_per_meter = drain_percent_per_meter
        self._charge_percent_per_second = charge_percent_per_second
        self._docking_seconds = docking_seconds
        # Tracked at full precision; the published level is a whole percent
        # (like the real robot's), re-published only when it changes.
        self._level = float(telemetry.state.battery_level)
        self._task: asyncio.Task | None = None

    @property
    def level(self) -> int:
        return round(self._level)

    @property
    def charging(self) -> bool:
        return self._telemetry.state.charging

    def set_level(self, level: float) -> None:
        self._set(level)

    def drain(self, distance_m: float) -> None:
        self._set(self._level - distance_m * self._drain_percent_per_meter)

    def dock(self) -> None:
        """Starts docking: charging begins after the docking delay and runs until full."""
        self.undock()
        self._task = asyncio.create_task(self._dock_and_charge())

    def undock(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
        if self._telemetry.state.charging:
            self._telemetry.set_charging(False)

    def _set(self, level: float) -> None:
        previous = round(self._level)
        self._level = min(100.0, max(0.0, level))
        if round(self._level) != previous:
            self._telemetry.set_battery_level(round(self._level))

    async def _dock_and_charge(self) -> None:
        await asyncio.sleep(self._docking_seconds)
        self._telemetry.set_charging(True)
        while self._level < 100:
            await asyncio.sleep(CHARGE_TICK_SECONDS)
            self._set(self._level + self._charge_percent_per_second * CHARGE_TICK_SECONDS)
