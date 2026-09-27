"""FastAPI application exposing the simulated robot's HTTP API."""

from sse_starlette.sse import EventSourceResponse
from fastapi import FastAPI

from pudubot2_sim.config import Config
from pudubot2_sim.telemetry import TelemetryBroker

# Comfortably under fleet_adapter_pudu's default 30s sse_stale_after, so its
# SSE connection is never mistaken for stale and reconnected unnecessarily.
HEARTBEAT_INTERVAL_SECONDS = 10


def create_app(config: Config) -> FastAPI:
    app = FastAPI(title=f"pudubot2_sim ({config.robot_name})")
    app.state.telemetry = TelemetryBroker(config)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "robot_name": config.robot_name}

    @app.get("/events")
    async def events() -> EventSourceResponse:
        return EventSourceResponse(
            app.state.telemetry.subscribe(), ping=HEARTBEAT_INTERVAL_SECONDS
        )

    return app
