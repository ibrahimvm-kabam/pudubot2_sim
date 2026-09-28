"""Per-map waypoint data, loaded from config."""

from __future__ import annotations

from dataclasses import dataclass

from pudubot2_sim.config import Config


@dataclass
class Waypoint:
    id: str
    x: float
    y: float
    theta: float


@dataclass
class MapConfig:
    waypoints: list[Waypoint]
    charger_waypoint_id: str | None

    def find_waypoint(self, waypoint_id: str) -> Waypoint | None:
        return next((w for w in self.waypoints if w.id == waypoint_id), None)

    def charger_waypoint(self) -> Waypoint | None:
        if self.charger_waypoint_id is None:
            return None
        return self.find_waypoint(self.charger_waypoint_id)


def load_maps(config: Config) -> dict[str, MapConfig]:
    maps: dict[str, MapConfig] = {}
    for map_name, map_config in config.maps.items():
        waypoints = [
            Waypoint(id=w["id"], x=w["x"], y=w["y"], theta=w["theta"])
            for w in map_config.get("waypoints", [])
        ]
        maps[map_name] = MapConfig(
            waypoints=waypoints,
            charger_waypoint_id=map_config.get("charger_waypoint"),
        )
    return maps
