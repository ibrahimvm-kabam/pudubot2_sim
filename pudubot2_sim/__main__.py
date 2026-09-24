"""Runs the simulated robot's HTTP server."""

import argparse
from pathlib import Path

import uvicorn

from pudubot2_sim.app import create_app
from pudubot2_sim.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulated Pudu robot")
    parser.add_argument("--config", type=Path, default=Path("configs/config.yaml"))
    args = parser.parse_args()

    config = load_config(args.config)
    app = create_app(config)
    uvicorn.run(app, host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    main()
