"""Loads the simulator's YAML configuration file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Pose:
    x: float
    y: float
    theta: float


@dataclass
class Config:
    robot_name: str
    port: int
    initial_map: str
    initial_pose: Pose
    initial_battery: float
    floorplans_dir: Path
    # Raw per-map config (waypoints, floorplan calibration, etc.), structured
    # and consumed by the modules that own each concern.
    maps: dict[str, Any]


def load_config(path: Path) -> Config:
    with open(path) as config_file:
        raw = yaml.safe_load(config_file)

    initial_state = raw["initial_state"]
    pose = initial_state["pose"]

    return Config(
        robot_name=raw["robot_name"],
        port=raw["port"],
        initial_map=initial_state["map"],
        initial_pose=Pose(x=pose["x"], y=pose["y"], theta=pose["theta"]),
        initial_battery=initial_state["battery"],
        floorplans_dir=Path(raw.get("floorplans_dir", "floorplans")),
        maps=raw.get("maps", {}),
    )
