"""Generates per-map occupancy grids from floorplan scans.

Real Pudu robots build their occupancy map from onboard SLAM. This
simulator instead derives one from a building's floorplan scans, so
navigation planning has walls to route around without needing a real
robot to have mapped the space first.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from pudubot2_sim.config import Config

# Grayscale intensity below which a floorplan pixel is treated as a wall.
OCCUPIED_THRESHOLD = 128


@dataclass
class OccupancyGrid:
    """A binary occupancy grid in the map's real-world coordinate frame.

    Follows the ROS map_server convention: `origin` is the world
    coordinate of the grid's bottom-left cell.
    """

    resolution: float  # meters per cell
    origin_x: float
    origin_y: float
    occupied: np.ndarray  # 2D bool array, True where a robot cannot pass

    def is_occupied(self, x: float, y: float) -> bool:
        height, width = self.occupied.shape
        col = int((x - self.origin_x) / self.resolution)
        row = height - 1 - int((y - self.origin_y) / self.resolution)
        if not (0 <= row < height and 0 <= col < width):
            return True
        return bool(self.occupied[row, col])


def build_occupancy_grid(
    floorplan_path: Path,
    resolution: float,
    origin_x: float,
    origin_y: float,
    rotation_degrees: float = 0.0,
) -> OccupancyGrid:
    image = Image.open(floorplan_path).convert("L")
    if rotation_degrees:
        image = image.rotate(rotation_degrees, expand=True)
    occupied = np.array(image) < OCCUPIED_THRESHOLD
    return OccupancyGrid(resolution, origin_x, origin_y, occupied)


def load_occupancy_grids(config: Config) -> dict[str, OccupancyGrid]:
    """Builds an occupancy grid for every map with a `floorplan` block configured.

    Maps without one are simply absent from the result - the navigation
    planner falls back to straight-line movement for those.
    """
    grids: dict[str, OccupancyGrid] = {}
    for map_name, map_config in config.maps.items():
        floorplan = map_config.get("floorplan")
        if floorplan is None:
            continue
        origin = floorplan["origin"]
        grids[map_name] = build_occupancy_grid(
            floorplan_path=config.floorplans_dir / floorplan["file"],
            resolution=floorplan["resolution"],
            origin_x=origin["x"],
            origin_y=origin["y"],
            rotation_degrees=floorplan.get("rotation", 0.0),
        )
    return grids
