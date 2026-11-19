# Backend and API

Python backend (`backend/` in the repository).

What it does:

- Serves the REST API.
- Subscribes to MQTT and stores the readings.
- Applies the check-in and reward rules.
- Fetches external data.

> **OpenAPI:** once the backend runs, the interactive API documentation is served at `http://<host>:<port>/docs`, and the raw spec at `/openapi.json`. That spec is the authoritative reference. The tables below are an overview. ([#10](https://github.com/julianzangl/NatureCheckpoint/issues/10))

## REST endpoints

| Method | Endpoint | Auth | Purpose | Issue |
|---|---|---|---|---|
| `GET` | `/health` | - | Service status | [#10](https://github.com/julianzangl/NatureCheckpoint/issues/10) |
| `GET` | `/api/stations` | - | Stations with coordinates and latest conditions | [#14](https://github.com/julianzangl/NatureCheckpoint/issues/14) |
| `POST` | `/api/checkins` | Visitor ID | Collect a stamp | [#16](https://github.com/julianzangl/NatureCheckpoint/issues/16) |
| `GET` | `/api/progress` | Visitor ID | Monthly stamps, visited stations, reward status | [#19](https://github.com/julianzangl/NatureCheckpoint/issues/19) |
| `GET` | `/api/reports/daily` | - | Daily avg / median / min / max / trend | [#25](https://github.com/julianzangl/NatureCheckpoint/issues/25) |

Sensor readings are **not** sent over REST. They arrive via MQTT and are written to InfluxDB by the `mqtt-ingest` service ([#11](https://github.com/julianzangl/NatureCheckpoint/issues/11)).

### Web pages

Served by the same FastAPI app (Jinja2 templates):

| Path | Page | Issue |
|---|---|---|
| `/c/<station_id>` | Check-in page, opened by the NFC tag | [#18](https://github.com/julianzangl/NatureCheckpoint/issues/18) |
| `/progress` | Monthly progress | [#19](https://github.com/julianzangl/NatureCheckpoint/issues/19) |
| `/map` | Checkpoint map | [#23](https://github.com/julianzangl/NatureCheckpoint/issues/23) |
| `/privacy` | Privacy notice | [#34](https://github.com/julianzangl/NatureCheckpoint/issues/34) |

### Examples

`POST /api/checkins`. The visitor is identified by the `nc_visitor` cookie, not by a body field.

```json
{ "station_id": "station-1" }
```

Response:

```json
{ "status": "stamped", "station": "Checkpoint 1", "stamps_this_month": 4, "goal": 6 }
```

`GET /api/progress`

```json
{
  "month": "2026-11",
  "stamps": 4,
  "goal": 6,
  "stations_visited": ["station-1"],
  "stations_missing": ["station-2"],
  "reward_status": "locked"
}
```

## MQTT topics

| Topic | Direction | Payload |
|---|---|---|
| `naturecheckpoint/<station_id>/readings` | Pi → backend | Sensor sample (see [Sensor Node](Sensor-Node#sampling-loop)) |
| `naturecheckpoint/<station_id>/health` | Pi → backend | `{ "station_id": "station-1", "timestamp": "...", "cpu_temp": 52.1, "load1": 0.31, "uptime_s": 3600 }` |

All messages use QoS 1 and are not retained.

## Authentication

- **Devices:** each checkpoint has its own Mosquitto user (`allow_anonymous false`). The password file is not committed.
- **Visitors:** on the first visit the backend sets a random UUID4 in the `nc_visitor` cookie (`HttpOnly`, `SameSite=Lax`, valid 1 year). No name, email or location is stored. ([#15](https://github.com/julianzangl/NatureCheckpoint/issues/15))

## Check-in rules

([#17](https://github.com/julianzangl/NatureCheckpoint/issues/17))

- A check-in is **qualifying** if it is the visitor's first one at that station on that day. "Day" is computed in Europe/Madrid; timestamps are stored in UTC.
- A repeated tap returns `"status": "already_stamped"`, shown as a friendly message, and adds no stamp.
- A rate limit of max. 10 check-in requests per visitor per minute rejects bursts.
- Unknown stations and malformed payloads are rejected.

## Reward rule

([#20](https://github.com/julianzangl/NatureCheckpoint/issues/20))

- **Goal:** 6 qualifying stamps in a calendar month, at **at least 2 different stations**.
- When reached, the visitor gets **one** single-use mock voucher code for that month (`NC-` plus 8 random characters).
- Progress resets at the start of each month.
- Thresholds are configurable.

With two checkpoints and one stamp per station and day, the goal needs at least 3 days of visits.

Rewards are **simulated**. There are no real partner agreements in the MVP.
