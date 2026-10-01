"""FastAPI application exposing the simulated robot's HTTP API."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from pudubot2_sim.battery import simulate_battery
from pudubot2_sim.config import Config, Pose
from pudubot2_sim.mapping import load_maps
from pudubot2_sim.navigation import NavigationController
from pudubot2_sim.telemetry import TelemetryBroker

# Comfortably under fleet_adapter_pudu's default 30s sse_stale_after, so its
# SSE connection is never mistaken for stale and reconnected unnecessarily.
HEARTBEAT_INTERVAL_SECONDS = 10

# How long a simulated map switch takes before ActiveMap/SwitchMapResult fire.
MAP_SWITCH_DELAY_SECONDS = 2.0

# How long a simulated relocalization takes before the robot reports localized again.
LOCALIZATION_DELAY_SECONDS = 2.0


class MapSwitchRequest(BaseModel):
    mapName: str


class NavigationStartRequest(BaseModel):
    waypointId: str


class LocalizationByPoseRequest(BaseModel):
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0


class LocalizationByWaypointRequest(BaseModel):
    waypoint: str


class UserAcknowledgementRequest(BaseModel):
    user_acknowledgment: bool


class DeliveryItemsRequest(BaseModel):
    delivery_items: list[str]


class EstopRequest(BaseModel):
    estop: bool


class BatteryLevelRequest(BaseModel):
    level: float = Field(ge=0, le=100)


class NavigationStatusRequest(BaseModel):
    # Names match NavigationStatus in pudubot2_adapter.
    status: Literal[
        "ARRIVED", "MOVING", "APPROACHING", "AVOID", "STUCK", "PAUSE", "RESUME",
        "FAIL_ESCAPE", "TO_ESCAPE", "ESCAPING", "ESCAPE_FINISHED", "RE_PLANNING",
        "UNKNOWN",
    ]  # fmt: skip


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

    @app.get("/localization/status")
    def localization_status() -> dict:
        return {"localized": telemetry.state.localized}

    @app.post("/localization/by_pose")
    async def localization_by_pose(body: LocalizationByPoseRequest) -> dict:
        asyncio.create_task(_relocalize(telemetry, Pose(**body.model_dump())))
        return {"relocating": True}

    @app.post("/localization/by_waypoint_name")
    async def localization_by_waypoint_name(body: LocalizationByWaypointRequest) -> dict:
        waypoint = maps[telemetry.state.active_map].find_waypoint(body.waypoint)
        if waypoint is None:
            raise HTTPException(status_code=400, detail=f"Unknown waypoint: {body.waypoint}")
        asyncio.create_task(
            _relocalize(telemetry, Pose(waypoint.x, waypoint.y, waypoint.theta))
        )
        return {"relocating": True}

    @app.post("/user_interaction/command")
    def user_interaction_command(body: UserAcknowledgementRequest) -> dict:
        telemetry.set_awaiting_user_input(body.user_acknowledgment)
        return {"received": True}

    @app.get("/user_interaction/state")
    def user_interaction_state() -> dict:
        return {"state": "not_implemented"}

    @app.post("/set_delivery_items")
    def set_delivery_items(body: DeliveryItemsRequest) -> dict:
        telemetry.state.delivery_items = body.delivery_items
        return {"received": True}

    @app.get("/audio/play")
    def audio_play() -> dict:
        return {"Audio Triggered": True}

    @app.get("/audio/stop")
    def audio_stop() -> dict:
        return {"Audio Stopped": True}

    # Test controls: actions that happen on the physical robot rather than over
    # the adapter's API, so an automated test can drive them.

    @app.get("/sim/state")
    def sim_state() -> dict:
        return asdict(telemetry.state)

    @app.post("/sim/user_acknowledgement")
    def sim_user_acknowledgement() -> dict:
        """Simulates the user tapping Done, which is only visible while awaiting input."""
        if not telemetry.state.awaiting_user_input:
            raise HTTPException(status_code=409, detail="Not awaiting user input")
        telemetry.set_awaiting_user_input(False)
        return {"acknowledged": True}

    @app.post("/sim/estop")
    def sim_estop(body: EstopRequest) -> dict:
        if body.estop:
            navigation.stop()
        telemetry.set_estop(body.estop)
        return {"estop": body.estop}

    @app.post("/sim/battery")
    def sim_battery(body: BatteryLevelRequest) -> dict:
        telemetry.set_battery_level(body.level)
        return {"battery": telemetry.state.battery_percentage}

    @app.post("/sim/navigation_status")
    def sim_navigation_status(body: NavigationStatusRequest) -> dict:
        """Halts motion and reports the given status, e.g. STUCK."""
        navigation.stop()
        telemetry.set_navigation_status(body.status)
        return {"status": body.status}

    return app


async def _switch_map(telemetry: TelemetryBroker, map_name: str) -> None:
    await asyncio.sleep(MAP_SWITCH_DELAY_SECONDS)
    telemetry.publish_switch_map_result(True)
    telemetry.set_active_map(map_name)


async def _relocalize(telemetry: TelemetryBroker, pose: Pose) -> None:
    telemetry.set_localized(False)
    await asyncio.sleep(LOCALIZATION_DELAY_SECONDS)
    telemetry.set_pose(pose)
    telemetry.set_localized(True)
