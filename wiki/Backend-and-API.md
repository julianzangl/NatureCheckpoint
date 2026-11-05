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
| `POST` | `/api/readings` | Device key | Store sensor readings over HTTP | [#11](https://github.com/julianzangl/NatureCheckpoint/issues/11) |
| `GET` | `/api/stations` | - | Stations with coordinates and latest conditions | [#14](https://github.com/julianzangl/NatureCheckpoint/issues/14) |
| `POST` | `/api/checkins` | Visitor ID | Collect a stamp | [#16](https://github.com/julianzangl/NatureCheckpoint/issues/16) |
| `GET` | `/api/progress` | Visitor ID | Monthly stamps, visited stations, reward status | [#19](https://github.com/julianzangl/NatureCheckpoint/issues/19) |
| `GET` | `/api/reports/daily` | - | Daily avg / median / min / max / trend | [#25](https://github.com/julianzangl/NatureCheckpoint/issues/25) |

### Examples (planned)

`POST /api/checkins`

```json
{ "station_id": "station-1", "tag_payload": "...", "session_id": "3f9c..." }
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
  "stations_visited": ["station-1", "station-2"],
  "reward_status": "locked"
}
```

## MQTT topics

| Topic | Direction | Payload |
|---|---|---|
| `naturecheckpoint/<station_id>/readings` | Pi → backend | Sensor sample (see [Sensor Node](Sensor-Node#sampling-loop)) |
| `naturecheckpoint/<station_id>/health` | Pi → backend | `{ "cpu_temp": 52.1, "load": 0.3, "uptime_s": 3600 }` |

## Authentication

- **Devices:** sensor nodes send a device API key from `.env`. Requests without a valid key are rejected.
- **Visitors:** on the first visit the backend creates a random pseudonymous ID, stored in a cookie or token. No name, email or location is stored. ([#15](https://github.com/julianzangl/NatureCheckpoint/issues/15))

## Check-in rules

([#17](https://github.com/julianzangl/NatureCheckpoint/issues/17))

- A check-in is **qualifying** if it is the visitor's first one at that station on that day.
- A repeated tap returns a friendly *"already stamped today"* message and adds no stamp.
- A basic rate limit rejects bursts of requests.
- Unknown stations and malformed payloads are rejected.

## Reward rule

([#20](https://github.com/julianzangl/NatureCheckpoint/issues/20))

- **Goal:** 6 qualifying stamps in a calendar month, at **at least 2 different stations**.
- When reached, the visitor gets **one** single-use mock voucher code for that month.
- Progress resets at the start of each month.
- Thresholds are configurable.

With two checkpoints and one stamp per station and day, the goal needs at least 3 days of visits.

Rewards are **simulated**. There are no real partner agreements in the MVP.
