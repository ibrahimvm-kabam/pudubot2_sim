"""FastAPI application exposing the simulated robot's HTTP API."""

import asyncio
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from pudubot2_sim.config import Config
from pudubot2_sim.mapping import load_maps
from pudubot2_sim.telemetry import TelemetryBroker

# Comfortably under fleet_adapter_pudu's default 30s sse_stale_after, so its
# SSE connection is never mistaken for stale and reconnected unnecessarily.
HEARTBEAT_INTERVAL_SECONDS = 10

# How long a simulated map switch takes before ActiveMap/SwitchMapResult fire.
MAP_SWITCH_DELAY_SECONDS = 2.0


class MapSwitchRequest(BaseModel):
    mapName: str


def create_app(config: Config) -> FastAPI:
    app = FastAPI(title=f"pudubot2_sim ({config.robot_name})")
    telemetry = TelemetryBroker(config)
    maps = load_maps(config)
    app.state.telemetry = telemetry
    app.state.maps = maps

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "robot_name": config.robot_name}

    @app.get("/events")
    async def events() -> EventSourceResponse:
        return EventSourceResponse(
            telemetry.subscribe(), ping=HEARTBEAT_INTERVAL_SECONDS
        )

    @app.get("/map/current")
    def map_current() -> dict:
        return {"map": telemetry.state.active_map}

    @app.get("/map/list")
    def map_list() -> dict:
        return {"maps": list(maps.keys())}

    @app.get("/map/waypoints")
    def map_waypoints() -> dict:
        current_map = maps[telemetry.state.active_map]
        if not current_map.waypoints:
            raise HTTPException(status_code=503, detail="Waypoints not yet available")
        return {"waypoints": [asdict(waypoint) for waypoint in current_map.waypoints]}

    @app.get("/map/charger_waypoint")
    def map_charger_waypoint() -> dict:
        charger = maps[telemetry.state.active_map].charger_waypoint()
        return asdict(charger) if charger else {}

    @app.post("/map/switch")
    async def map_switch(body: MapSwitchRequest) -> dict:
        if body.mapName not in maps:
            raise HTTPException(status_code=400, detail=f"Unknown map: {body.mapName}")
        asyncio.create_task(_switch_map(telemetry, body.mapName))
        return {"switching": True}

    return app


async def _switch_map(telemetry: TelemetryBroker, map_name: str) -> None:
    await asyncio.sleep(MAP_SWITCH_DELAY_SECONDS)
    telemetry.publish_switch_map_result(True)
    telemetry.set_active_map(map_name)
