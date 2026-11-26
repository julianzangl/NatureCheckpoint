# Data and Dashboards

## Storage

| Store | Content | Issue |
|---|---|---|
| **InfluxDB** | Sensor readings and Pi health (`station_id` tag, timestamp) | [#11](https://github.com/julianzangl/NatureCheckpoint/issues/11) |
| **SQLite** | Stations, visitors, check-ins, vouchers | [#15](https://github.com/julianzangl/NatureCheckpoint/issues/15), [#16](https://github.com/julianzangl/NatureCheckpoint/issues/16) |

Both run locally. InfluxDB runs in Docker Compose, or natively on the demo Pi (`deploy/pi/provision_native.py`). Configuration: [Setup Guide](Setup-Guide).

InfluxDB schema:

| Measurement | Tags | Fields |
|---|---|---|
| `environment` | `station_id` | `temperature`, `humidity`, `light`, `condition` |
| `device_health` | `station_id` | `cpu_temp`, `load1`, `uptime_s` |
| `checkins` | `station_id` | `taps` (1 per tap), `stamps` (1 if the tap was a stamp). Written by the backend, no visitor ID. |

- Org: `naturecheckpoint`
- Bucket: `environment`
- Retention: 90 days

## Dashboards

| Dashboard | Audience | Content | Issue |
|---|---|---|---|
| Environmental (Grafana) | Park operators | Temperature, humidity, light over time per station; current rating; last-seen time | [#13](https://github.com/julianzangl/NatureCheckpoint/issues/13) |
| Operator (Grafana) | City operators, team | Taps and stamps today, stamps and taps per station per hour, latest device health, CPU temperature | [#24](https://github.com/julianzangl/NatureCheckpoint/issues/24), [#29](https://github.com/julianzangl/NatureCheckpoint/issues/29) |
| Visitor map (web app) | Visitors | Leaflet map of checkpoints, marker colour = rating | [#23](https://github.com/julianzangl/NatureCheckpoint/issues/23) |

Grafana is **provisioned from files**. After `docker compose up`, the data source and the dashboards are there without any clicking:

| File | Content |
|---|---|
| `deploy/grafana/provisioning/datasources/influxdb.yaml` | InfluxDB data source (Flux, `http://influxdb:8086`, token from `INFLUXDB_TOKEN` in `.env`) |
| `deploy/grafana/provisioning/dashboards/dashboards.yaml` | Loads every JSON file in `deploy/grafana/dashboards/` into the folder *NatureCheckpoint* |
| `deploy/grafana/dashboards/environment.json` | Environmental dashboard |
| `deploy/grafana/dashboards/operator.json` | Operator dashboard (check-ins, device health) |

### Environmental dashboard

http://localhost:3000/d/nc-environment (login `admin` / `GRAFANA_ADMIN_PASSWORD`). Refreshes every 30 s.

| Panel | Shows |
|---|---|
| Walk conditions now | Latest rating per station from the last 15 min: green GOOD, yellow FAIR, red POOR, grey SENSOR FAULT. *No data* means the station sent nothing for 15 min. |
| Last seen | Time of the last message (readings or health) per station |
| Temperature, Humidity, Light | History per station, averaged per time bucket |

The **Station** drop-down at the top filters all panels. Its values come from the `station_id` tags in InfluxDB, so a new station appears on its own.

**Changing the dashboard:** edit it in the UI, then *Export → Export as JSON* (do not tick "Export for sharing externally") and replace `deploy/grafana/dashboards/environment.json`. Keep the `uid` `nc-environment`, so links stay valid. Without that step, UI changes are lost when the volume is deleted.

Test data without a Pi: `python tools/fake_station.py` (see [Setup Guide](Setup-Guide)).

Check-in statistics never show individual visitor histories. Counts below a threshold are hidden.

### Visitor map

`/map` in the web app ([#23](https://github.com/julianzangl/NatureCheckpoint/issues/23)). Leaflet 1.9.4 with OpenStreetMap tiles; the page loads `GET /api/stations` and refreshes every 60 s.

| Marker colour | Meaning |
|---|---|
| green `#2e7d32` | good |
| yellow `#f9a825` | fair |
| red `#c62828` | poor |
| grey | sensor fault, or no data yet |

Tapping a marker shows the name, the latest temperature, humidity and light, and "updated x min ago". On phones the map fills most of the screen. Files: `backend/app/templates/map.html`, `backend/app/static/map.js`, `backend/app/static/map.css`.

## Analytics

([#25](https://github.com/julianzangl/NatureCheckpoint/issues/25))

Per station and day, the backend computes:

- average, median, min and max of temperature, humidity and light
- trend: `rising` / `falling` / `steady`, comparing the mean of the first and the last quarter of the day's readings (more than 5 % change counts as a trend)
- how many readings had each walk condition

`GET /api/reports/daily?station_id=station-1&date=2026-11-26` returns it (`app/services/reports.py`). The day is the calendar day in Europe/Madrid. Without InfluxDB the endpoint answers `503`.

## External data

([#26](https://github.com/julianzangl/NatureCheckpoint/issues/26))

| Source | Data | Use |
|---|---|---|
| [Open-Meteo](https://open-meteo.com/) | Weather and UV forecast (no API key) | Shown next to local readings |
| [Open Data Euskadi: air quality](https://opendata.euskadi.eus/catalogo/-/calidad-aire-en-euskadi-2026/) | Air quality (no API key) | Regional context |
| [Euskalmet](https://opendata.euskadi.eus/catalogo/-/estaciones-meteorologicas-lecturas-recogidas-en-2026/) *(optional)* | Official Basque weather data | Needs an API key with JWT signing, so only if time is left |
| [Bilbao Open Data: Anillo Verde (GR 228)](https://www.bilbao.eus/opendata/es/catalogo/dato-anillo-verde) | Green ring route | Optional map overlay |

Implemented in the MVP: **Open-Meteo**. `GET /api/weather` returns the current regional temperature, humidity, UV index and weather for the park (`app/services/weather.py`, cached 10 min, last value kept if the API fails). The map page shows it below the map as context: the checkpoints measure the microclimate on site, Open-Meteo the region. The other sources are future work.

External data is fetched periodically and cached. If an API fails, the app keeps working. API keys live only in `.env`.

**Important:** check-ins only count NatureCheckpoint users, not all park visitors.
