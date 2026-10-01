# pudubot2_sim

A simulated Pudu robot that speaks the same HTTP/SSE API as [`pudubot2_adapter`](https://github.com/ibrahimvm-kabam/pudubot2_adapter) (the Android app that runs on a real Pudu robot), so that [`fleet_adapter_pudu`](https://github.com/ibrahimvm-kabam/fleet_adapter_pudu) can be developed and tested against it without physical hardware.

It simulates navigation between waypoints, charging, localization, and the delivery/user-interaction workflow, exposing all of it over the same endpoints and server-sent events the real robot adapter uses.

## Status

Implemented, mirroring `pudubot2_adapter`'s endpoints:

| Area | Endpoints |
|---|---|
| Telemetry | `GET /events` (SSE; `{type, data, timestamp}` envelope, state seeded on connect, 10s heartbeat) |
| Maps | `GET /map/current`, `/map/list`, `/map/waypoints`, `/map/charger_waypoint`; `POST /map/switch` |
| Navigation | `GET /pose`, `/navigation/status`; `POST /navigation/start`, `/navigation/stop` (statuses `MOVING`, `APPROACHING`, `ARRIVED`; `PAUSE`/`RESUME` on e-stop) |
| Charging / battery | `GET /charge` (drive to the charger, dock, charge), `/battery/level`, `/battery/charging`; battery drains while moving |
| Localization | `GET /localization/status`; `POST /localization/by_pose`, `/localization/by_waypoint_name` |
| User interaction | `POST /user_interaction/command`, `/set_delivery_items`; `GET /user_interaction/state`; simulated "Done" tap |
| Audio | `GET /audio/play`, `/audio/stop` (stubs) |

Not implemented, because the real robot doesn't serve them either: `/set_delivery_status` and `/robot/app/audio/*` (both called by `fleet_adapter_pudu`, both 404 on the real robot).
`POST /set_delivery_items` also accepts a plain string (as `fleet_adapter_pudu` sends), which the real robot would reject.

### Fault injection (`/sim/*`, disable with `sim_api: false`)

| Endpoint | Body | Effect |
|---|---|---|
| `POST /sim/acknowledge` | none | Simulates the user tapping Done (or set `user_interaction.auto_acknowledge_seconds`) |
| `POST /sim/estop` | `{"estop": bool}` | Publishes `Estop`; pauses navigation while true |
| `POST /sim/localization` | `{"localized": bool}` | Forces `LocalizationStatus` |
| `POST /sim/battery` | `{"level": n}` | Sets the battery level |
| `POST /sim/navigation/fail` | `{"status": "STUCK"}` or `"FAIL_ESCAPE"` | Aborts the current navigation with that status (409 if not navigating) |
| `POST /sim/map_switch_failure` | `{"fail": bool}` | The next `/map/switch` publishes `SwitchMapResult: false` and keeps the map |

## Testing

```bash
pip install -e '.[test]'
pytest
```

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
