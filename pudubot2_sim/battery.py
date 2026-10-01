"""Simulates battery drain while the robot is running and recovery while it is docked."""

import asyncio

from pudubot2_sim.telemetry import TelemetryBroker

TICK_SECONDS = 1.0
DRAIN_PERCENT_PER_SECOND = 0.003
CHARGE_PERCENT_PER_SECOND = 0.03


async def simulate_battery(telemetry: TelemetryBroker) -> None:
    while True:
        await asyncio.sleep(TICK_SECONDS)
        rate = (
            CHARGE_PERCENT_PER_SECOND
            if telemetry.state.charging
            else -DRAIN_PERCENT_PER_SECOND
        )
        level = telemetry.state.battery_level + rate * TICK_SECONDS
        telemetry.set_battery_level(min(100.0, max(0.0, level)))
