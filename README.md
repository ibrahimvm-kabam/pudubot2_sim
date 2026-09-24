# pudubot2_sim

A simulated Pudu robot that speaks the same HTTP/SSE API as [`pudubot2_adapter`](https://github.com/ibrahimvm-kabam/pudubot2_adapter) (the Android app that runs on a real Pudu robot), so that [`fleet_adapter_pudu`](https://github.com/ibrahimvm-kabam/fleet_adapter_pudu) can be developed and tested against it without physical hardware.

It generates a navigable occupancy map from a building's floorplan scans, then simulates navigation, charging, localization, and the delivery/user-interaction workflow, exposing all of it over the same endpoints and server-sent events the real robot adapter uses.

## Status

This repository is being built up incrementally, one capability per pull request. See the open and merged PRs for progress.
