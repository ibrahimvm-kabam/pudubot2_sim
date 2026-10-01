"""FastAPI application exposing the simulated robot's HTTP API."""

import asyncio
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from pudubot2_sim.battery import BatteryController
from pudubot2_sim.config import Config, Pose
from pudubot2_sim.interaction import UserInteractionController
from pudubot2_sim.localization import LocalizationController
from pudubot2_sim.mapping import load_maps
from pudubot2_sim.navigation import FAILURE_STATUSES, NavigationController
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


async def _json_body(request: Request) -> dict:
    """Parses a JSON object body; a missing or malformed one is a 400, like the real robot's."""
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Missing request body")
    return body


def _require(body: dict, field: str):
    if field not in body:
        raise HTTPException(status_code=400, detail=f"Missing field: {field}")
    return body[field]


def create_app(config: Config) -> FastAPI:
    app = FastAPI(title=f"pudubot2_sim ({config.robot_name})")
    telemetry = TelemetryBroker(config)
    maps = load_maps(config)
    battery = BatteryController(
        telemetry,
        config.battery_drain_percent_per_meter,
        config.charge_percent_per_second,
        config.docking_seconds,
    )
    navigation = NavigationController(
        telemetry, maps, config.navigation_speed_m_per_s, battery
    )
    localization = LocalizationController(telemetry, config.localization_delay_seconds)
    interaction = UserInteractionController(telemetry, config.auto_acknowledge_seconds)
    app.state.telemetry = telemetry
    app.state.maps = maps
    app.state.battery = battery
    app.state.navigation = navigation
    app.state.localization = localization
    app.state.interaction = interaction
    # Set by POST /sim/map_switch_failure; makes the next map switch fail.
    app.state.fail_next_map_switch = False

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
        succeed = not app.state.fail_next_map_switch
        app.state.fail_next_map_switch = False
        asyncio.create_task(_switch_map(telemetry, body.mapName, succeed))
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
        navigation.charge()
        return {"charging": True}

    @app.get("/battery/level")
    def battery_level() -> dict:
        return {"battery": battery.level}

    @app.get("/battery/charging")
    def battery_charging() -> dict:
        # The real robot also keys this one "battery".
        return {"battery": battery.charging}

    @app.get("/localization/status")
    def localization_status() -> dict:
        return {"localized": telemetry.state.localized}

    @app.post("/localization/by_pose")
    async def localization_by_pose(request: Request) -> dict:
        body = await _json_body(request)
        localization.relocalize(
            Pose(
                x=float(body.get("x", 0.0)),
                y=float(body.get("y", 0.0)),
                theta=float(body.get("theta", 0.0)),
            )
        )
        return {"relocating": True}

    @app.post("/localization/by_waypoint_name")
    async def localization_by_waypoint_name(request: Request) -> dict:
        body = await _json_body(request)
        waypoint = maps[telemetry.state.active_map].find_waypoint(
            str(body.get("waypoint", ""))
        )
        # An unknown waypoint is silently ignored by the real robot, which still
        # reports that it is relocating.
        if waypoint is not None:
            localization.relocalize(Pose(waypoint.x, waypoint.y, waypoint.theta))
        return {"relocating": True}

    @app.post("/user_interaction/command")
    async def user_interaction_command(request: Request) -> dict:
        body = await _json_body(request)
        waiting = _require(body, "user_acknowledgment")
        if not isinstance(waiting, bool):
            raise HTTPException(status_code=400, detail="user_acknowledgment must be a bool")
        interaction.set_waiting(waiting)
        return {"received": True}

    @app.get("/user_interaction/state")
    def user_interaction_state() -> dict:
        return {"state": "not_implemented"}

    @app.post("/set_delivery_items")
    async def set_delivery_items(request: Request) -> dict:
        body = await _json_body(request)
        items = _require(body, "delivery_items")
        # fleet_adapter_pudu sends a plain string; the real robot only accepts a
        # list, so tolerate both rather than 400 on every delivery.
        if isinstance(items, str):
            items = [items]
        if not isinstance(items, list):
            raise HTTPException(status_code=400, detail="delivery_items must be a list")
        interaction.delivery_items = [str(item) for item in items]
        return {"received": True}

    @app.get("/audio/play")
    def audio_play() -> dict:
        return {"Audio Triggered": True}

    @app.get("/audio/stop")
    def audio_stop() -> dict:
        return {"Audio Stopped": True}

    if config.enable_sim_api:
        _add_sim_routes(app)

    return app


def _add_sim_routes(app: FastAPI) -> None:
    """Fault injection and manual triggers; not part of the real robot's API."""
    telemetry: TelemetryBroker = app.state.telemetry

    @app.post("/sim/acknowledge")
    async def sim_acknowledge() -> dict:
        """Simulates the user tapping Done on the delivery tablet."""
        return {"acknowledged": app.state.interaction.acknowledge()}

    @app.post("/sim/estop")
    async def sim_estop(request: Request) -> dict:
        estop = _require(await _json_body(request), "estop")
        if not isinstance(estop, bool):
            raise HTTPException(status_code=400, detail="estop must be a bool")
        telemetry.set_estop(estop)
        return {"estop": estop}

    @app.post("/sim/localization")
    async def sim_localization(request: Request) -> dict:
        localized = _require(await _json_body(request), "localized")
        if not isinstance(localized, bool):
            raise HTTPException(status_code=400, detail="localized must be a bool")
        app.state.localization.set_localized(localized)
        return {"localized": localized}

    @app.post("/sim/battery")
    async def sim_battery(request: Request) -> dict:
        level = _require(await _json_body(request), "level")
        if isinstance(level, bool) or not isinstance(level, (int, float)):
            raise HTTPException(status_code=400, detail="level must be a number")
        app.state.battery.set_level(level)
        return {"battery": app.state.battery.level}

    @app.post("/sim/navigation/fail")
    async def sim_navigation_fail(request: Request) -> dict:
        body = await _json_body(request)
        status = body.get("status", "STUCK")
        if status not in FAILURE_STATUSES:
            raise HTTPException(
                status_code=400, detail=f"status must be one of {list(FAILURE_STATUSES)}"
            )
        if not app.state.navigation.fail(status):
            raise HTTPException(status_code=409, detail="Not navigating")
        return {"status": status}

    @app.post("/sim/map_switch_failure")
    async def sim_map_switch_failure(request: Request) -> dict:
        fail = _require(await _json_body(request), "fail")
        if not isinstance(fail, bool):
            raise HTTPException(status_code=400, detail="fail must be a bool")
        app.state.fail_next_map_switch = fail
        return {"fail_next_map_switch": fail}


async def _switch_map(
    telemetry: TelemetryBroker, map_name: str, succeed: bool = True
) -> None:
    await asyncio.sleep(MAP_SWITCH_DELAY_SECONDS)
    telemetry.publish_switch_map_result(succeed)
    if succeed:
        telemetry.set_active_map(map_name)
