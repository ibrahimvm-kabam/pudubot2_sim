# pudubot2_sim

A simulated Pudu robot that speaks the same HTTP/SSE API as [`pudubot2_adapter`](https://github.com/ibrahimvm-kabam/pudubot2_adapter) (the Android app that runs on a real Pudu robot), so that [`fleet_adapter_pudu`](https://github.com/ibrahimvm-kabam/fleet_adapter_pudu) can be developed and tested against it without physical hardware.

It simulates navigation between waypoints, charging, localization, and the delivery/user-interaction workflow, exposing all of it over the same endpoints and server-sent events the real robot adapter uses.

## Status

This repository is being built up incrementally, one capability per pull request. See the open and merged PRs for progress.

## Running

1. Copy `configs/sample_config.yaml` and adjust it for your deployment (robot name, port, initial map/pose/battery).
2. Build the image:
   ```bash
   docker build -t pudubot2_sim .
   ```
3. Run it, mounting your config over the in-image path (see `fleet_adapter_pudu` for the matching `robot_url` convention):
   ```bash
   docker run -it --rm --network=host \
       -v ./configs/config.yaml:/app/configs/config.yaml \
       pudubot2_sim
   ```
4. Check it's up: `curl http://localhost:7896/health`.

Alternatively, adjust the paths in `docker-compose.yml` and run `docker compose up`.
