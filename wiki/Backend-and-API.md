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
| `POST` | `/api/checkins` | Visitor ID | Collect a stamp with the phone | [#16](https://github.com/julianzangl/NatureCheckpoint/issues/16) |
| `POST` | `/api/checkins/card` | Device token | Collect a stamp with a card at a checkpoint reader | [#9](https://github.com/julianzangl/NatureCheckpoint/issues/9) |
| `GET` | `/api/progress` | Visitor ID | Monthly stamps, visited stations, reward status | [#19](https://github.com/julianzangl/NatureCheckpoint/issues/19) |
| `GET` | `/api/reports/daily` | - | Daily avg / median / min / max / trend | [#25](https://github.com/julianzangl/NatureCheckpoint/issues/25) |
| `GET` | `/api/weather` | - | Regional weather from Open-Meteo (cached 10 min) | [#26](https://github.com/julianzangl/NatureCheckpoint/issues/26) |

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

Response (`200`):

```json
{ "status": "stamped", "station": "Duck pond", "stamps_this_month": 4, "goal": 6 }
```

A second tap at the same station on the same day also returns `200`, but adds no stamp:

```json
{ "status": "already_stamped", "station": "Duck pond", "stamps_this_month": 4, "goal": 6 }
```

| Code | When |
|---|---|
| `404` | Unknown `station_id` |
| `422` | Malformed body (`station_id` missing or not `[A-Za-z0-9_-]{1,64}`, `tag_payload` longer than 512 characters) |
| `429` | More than 10 check-in requests from this visitor within 60 s |

A first-time visitor gets the `nc_visitor` cookie with the response. `goal` comes from `REWARD_STAMPS` (default 6).

`GET /api/stations` ([#14](https://github.com/julianzangl/NatureCheckpoint/issues/14))

```json
[
  {
    "station_id": "station-1",
    "name": "Duck pond",
    "lat": 43.2657,
    "lon": -2.9405,
    "description": "Checkpoint at the duck pond in the centre of Parque de Doña Casilda Iturrizar.",
    "latest": {
      "temperature": 17.4,
      "humidity": 62.0,
      "light": 540.0,
      "condition": "good",
      "timestamp": "2026-11-19T10:00:00Z"
    }
  }
]
```

- The stations come from `deploy/stations.json`. The backend reads the file on every start and inserts or updates the stations in SQLite (`Station` table). Stations removed from the file stay in the database, because check-ins may refer to them. In Docker the file is mounted read-only at `/config/stations.json` (`STATIONS_FILE`).
- `latest` is the newest MQTT message of the station from InfluxDB (`app/services/influx.py`). A sensor that failed in that message is `null`; older values are not mixed in. `latest` is `null` if the station sent nothing for 30 days, or if InfluxDB is not reachable (the list still loads).
- The coordinates of both demo checkpoints are in Parque de Doña Casilda Iturrizar, Bilbao. Adjust them in `deploy/stations.json` to the real spots before the demo.

`POST /api/checkins/card`, sent by the checkpoint Pi when a card is tapped. Header `Authorization: Bearer <DEVICE_TOKEN>`:

```json
{ "station_id": "station-1", "card_hash": "3f0c9a5e1b7d4c2a8e6f1a2b3c4d5e6f" }
```

The response is the same as for `/api/checkins`. `card_hash` is the salted SHA-256 of the card UID, made on the Pi. The first tap of an unknown card creates a pseudonymous visitor. A wrong or missing device token gives `401`.

Once the monthly goal is reached, both check-in responses contain the voucher:

```json
{ "status": "stamped", "station": "Duck pond", "stamps_this_month": 6, "goal": 6, "reward": { "code": "NC-7K2QX9AB", "month": "2026-11" } }
```

`GET /api/progress` (visitor from the cookie; page: `/progress`)

```json
{
  "month": "2026-11",
  "stamps": 4,
  "goal": 6,
  "stations_visited": ["station-1"],
  "stations_missing": ["station-2"],
  "reward_status": "locked",
  "voucher_code": null
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
- **Checkpoints (card check-ins):** shared secret `DEVICE_TOKEN` as a Bearer token.
- **Visitors:** on the first visit the backend sets a random UUID4 in the `nc_visitor` cookie (`HttpOnly`, `SameSite=Lax`, valid 1 year). No name, email or location is stored. ([#15](https://github.com/julianzangl/NatureCheckpoint/issues/15))

## Check-in rules

([#17](https://github.com/julianzangl/NatureCheckpoint/issues/17))

- **Qualifying check-in:** the visitor's first check-in at that station on that day. "Day" is computed in Europe/Madrid; timestamps are stored in UTC (`app/services/rules.py`).
- **Database guarantee:** a partial unique index on `(visitor_id, station_id, local_date) WHERE qualifying = 1` ensures that two simultaneous taps can never both count.
- **Repeated taps:** stored as non-qualifying (so the statistics see every tap). They return `"status": "already_stamped"`, shown as a friendly message, and add no stamp.
- **Rate limit:** max. `CHECKIN_RATE_LIMIT` (default 10) check-in requests per visitor within `CHECKIN_RATE_WINDOW_S` (default 60 s), otherwise `429`. The limiter is in memory (`app/services/ratelimit.py`), which is enough for one backend process. A visitor who deletes the cookie gets a new identity and a fresh limit; that is accepted for the MVP.
- **Rejected requests:** unknown stations get `404`, malformed payloads `422`.
- **Monthly count:** `stamps_this_month` counts qualifying check-ins in the current calendar month (Europe/Madrid).

## Reward rule

([#20](https://github.com/julianzangl/NatureCheckpoint/issues/20))

- **Goal:** 6 qualifying stamps in a calendar month, at **at least 2 different stations**.
- When reached, the visitor gets **one** single-use mock voucher code for that month (`NC-` plus 8 random characters).
- Progress resets at the start of each month.
- Thresholds are configurable (`REWARD_STAMPS`, `REWARD_MIN_STATIONS`).

With two checkpoints and one stamp per station and day, the goal needs at least 3 days of visits.

Implementation: `app/services/rewards.py`. The voucher is issued in the check-in that reaches the goal and stored in the `Voucher` table (unique per visitor and month, so it is issued only once). Phone visitors see it on the check-in page and on `/progress`, card visitors on the checkpoint's LCD. `REWARD_STAMPS` and `REWARD_MIN_STATIONS` change the rule.

Rewards are **simulated**. There are no real partner agreements in the MVP.
