# pudubot2_sim

A simulated Pudu robot that speaks the same HTTP/SSE API as [`pudubot2_adapter`](https://github.com/ibrahimvm-kabam/pudubot2_adapter) (the Android app that runs on a real Pudu robot), so that [`fleet_adapter_pudu`](https://github.com/ibrahimvm-kabam/fleet_adapter_pudu) can be developed and tested against it without physical hardware.

It simulates navigation between waypoints, charging, localization, and the delivery/user-interaction workflow, exposing all of it over the same endpoints and server-sent events the real robot adapter uses.

## Status

All `pudubot2_adapter` endpoints used by the Android app and `fleet_adapter_pudu` are implemented. See [Supported API](#supported-api) for the exceptions.

## Supported API

The sim implements every endpoint of `pudubot2_adapter`, with the same request and response shapes, plus the same SSE event types on `/events` (`pose`, `NavigationStatus`, `LocalizationStatus`, `ActiveMap`, `UserAcknowledgementStatus`, `BatteryLevel`, `ChargingStatus`, `SwitchMapResult`) and an `Estop` event that the real robot does not currently send.

Known differences from the real robot, chosen to make failures visible in tests:

- Unknown waypoint or map names, and `/charge` on a map with no charger, return HTTP 400. The real app accepts the request and the robot silently fails to move.
- `/set_delivery_status` is not implemented, because `pudubot2_adapter` does not implement it (HTTP 404).
- `/set_delivery_items` requires `delivery_items` to be a list of strings, as the real app does.
- Battery drains slowly while idle and recovers while docked.

## Test controls

Actions that occur on the physical robot rather than through the adapter's API are exposed under `/sim`:

| Endpoint | Effect |
|---|---|
| `GET /sim/state` | Full simulated robot state, including `delivery_items`. |
| `POST /sim/user_acknowledgement` | The user taps Done. Returns 409 unless the robot is awaiting user input. |
| `POST /sim/estop` `{"estop": bool}` | Sets the estop state. Engaging it also halts navigation. |
| `POST /sim/battery` `{"level": 0-100}` | Sets the battery level. |
| `POST /sim/navigation_status` `{"status": "STUCK"}` | Halts motion and reports the given navigation status. |

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

## Testing

```bash
pip install -e ".[dev]"
pytest
```

The tests start the sim on a local port and exercise it over real HTTP and SSE.

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
