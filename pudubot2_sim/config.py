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
    navigation_speed_m_per_s: float
    # Raw per-map config (waypoint list, charger waypoint id), parsed into
    # structured MapConfig objects by pudubot2_sim.mapping.
    maps: dict[str, Any]
    # Battery behaviour (percent units, matching the real adapter's 0-100 scale).
    battery_drain_percent_per_meter: float = 0.1
    charge_percent_per_second: float = 1.0
    docking_seconds: float = 2.0
    # How long a manual relocalization takes before LocalizationStatus goes true.
    localization_delay_seconds: float = 2.0
    # Simulated "Done" tap on the delivery tablet. None = wait for POST /sim/acknowledge.
    auto_acknowledge_seconds: float | None = None
    # Exposes the /sim/* fault-injection endpoints.
    enable_sim_api: bool = True


def load_config(path: Path) -> Config:
    with open(path) as config_file:
        raw = yaml.safe_load(config_file)

    initial_state = raw["initial_state"]
    pose = initial_state["pose"]
    battery = raw.get("battery", {})

    return Config(
        robot_name=raw["robot_name"],
        port=raw["port"],
        initial_map=initial_state["map"],
        initial_pose=Pose(x=pose["x"], y=pose["y"], theta=pose["theta"]),
        initial_battery=initial_state["battery"],
        navigation_speed_m_per_s=raw.get("navigation_speed_m_per_s", 0.4),
        maps=raw.get("maps", {}),
        battery_drain_percent_per_meter=battery.get("drain_percent_per_meter", 0.1),
        charge_percent_per_second=battery.get("charge_percent_per_second", 1.0),
        docking_seconds=battery.get("docking_seconds", 2.0),
        localization_delay_seconds=raw.get("localization", {}).get("delay_seconds", 2.0),
        auto_acknowledge_seconds=raw.get("user_interaction", {}).get(
            "auto_acknowledge_seconds"
        ),
        enable_sim_api=raw.get("sim_api", True),
    )
