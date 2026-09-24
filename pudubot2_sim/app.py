"""FastAPI application exposing the simulated robot's HTTP API."""

from fastapi import FastAPI

from pudubot2_sim.config import Config
from pudubot2_sim.mapping.floorplan import load_occupancy_grids


def create_app(config: Config) -> FastAPI:
    app = FastAPI(title=f"pudubot2_sim ({config.robot_name})")
    app.state.occupancy_grids = load_occupancy_grids(config)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "robot_name": config.robot_name}

    return app
