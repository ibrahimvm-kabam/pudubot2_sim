"""FastAPI application exposing the simulated robot's HTTP API."""

from fastapi import FastAPI

from pudubot2_sim.config import Config


def create_app(config: Config) -> FastAPI:
    app = FastAPI(title=f"pudubot2_sim ({config.robot_name})")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "robot_name": config.robot_name}

    return app
