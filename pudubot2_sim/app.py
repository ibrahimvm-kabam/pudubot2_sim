"""FastAPI application exposing the simulated robot's HTTP API."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from pudubot2_sim.battery import simulate_battery
from pudubot2_sim.config import Config
from pudubot2_sim.mapping import load_maps
from pudubot2_sim.navigation import NavigationController
from pudubot2_sim.telemetry import TelemetryBroker

# Comfortably under fleet_adapter_pudu's default 30s sse_stale_after, so its
# SSE connection is never mistaken for stale and reconnected unnecessarily.
HEARTBEAT_INTERVAL_SECONDS = 10

# How long a simulated map switch takes before ActiveMap/SwitchMapResult fire.
MAP_SWITCH_DELAY_SECONDS = 2.0


class MapSwitchRequest(BaseModel):
    mapName: str


class NavigationStartRequest(BaseModel):
    waypointId: str


def create_app(config: Config) -> FastAPI:
    telemetry = TelemetryBroker(config)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        battery_task = asyncio.create_task(simulate_battery(telemetry))
        yield
        battery_task.cancel()

    app = FastAPI(title=f"pudubot2_sim ({config.robot_name})", lifespan=lifespan)
    maps = load_maps(config)
    navigation = NavigationController(telemetry, maps, config.navigation_speed_m_per_s)
    app.state.telemetry = telemetry
    app.state.maps = maps
    app.state.navigation = navigation

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

    @app.get("/pose")
    def pose() -> dict:
        return asdict(telemetry.state.pose)

    @app.get("/navigation/status")
    def navigation_status() -> dict:
        return {"status": telemetry.state.navigation_status}

    @app.post("/navigation/start")
    async def navigation_start(body: NavigationStartRequest) -> dict:
        if not navigation.start(body.waypointId):
            raise HTTPException(
                status_code=400, detail=f"Unknown waypoint: {body.waypointId}"
            )
        return {"started": True}

    @app.post("/navigation/stop")
    async def navigation_stop() -> dict:
        navigation.stop()
        return {"stopped": True}

    @app.get("/charge")
    async def charge() -> dict:
        if not navigation.charge():
            raise HTTPException(status_code=400, detail="No charger on the active map")
        return {"charging": True}

    @app.get("/battery/level")
    def battery_level() -> dict:
        return {"battery": telemetry.state.battery_percentage}

    # The real robot reports charging under the "battery" key as well.
    @app.get("/battery/charging")
    def battery_charging() -> dict:
        return {"battery": telemetry.state.charging}

    return app


async def _switch_map(telemetry: TelemetryBroker, map_name: str) -> None:
    await asyncio.sleep(MAP_SWITCH_DELAY_SECONDS)
    telemetry.publish_switch_map_result(True)
    telemetry.set_active_map(map_name)
