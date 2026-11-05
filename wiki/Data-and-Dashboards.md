# Data and Dashboards

## Storage

| Store | Content | Issue |
|---|---|---|
| **InfluxDB** | Sensor readings and Pi health (`station_id` tag, timestamp) | [#11](https://github.com/julianzangl/NatureCheckpoint/issues/11) |
| **SQLite** | Stations, visitors, check-ins, vouchers | [#15](https://github.com/julianzangl/NatureCheckpoint/issues/15), [#16](https://github.com/julianzangl/NatureCheckpoint/issues/16) |

Both run locally. InfluxDB runs in Docker Compose. Configuration: [Setup Guide](Setup-Guide).

## Dashboards

| Dashboard | Audience | Content | Issue |
|---|---|---|---|
| Environmental (Grafana) | Park operators | Temperature, humidity, light over time per station; current rating; last-seen time | [#13](https://github.com/julianzangl/NatureCheckpoint/issues/13) |
| Check-in statistics | City operators | Check-ins per station per day/week, returning visitors | [#24](https://github.com/julianzangl/NatureCheckpoint/issues/24) |
| Pi health | Team / operators | CPU temperature, load, online/offline per station | [#29](https://github.com/julianzangl/NatureCheckpoint/issues/29) |
| Visitor map (web app) | Visitors | Leaflet map of checkpoints, marker colour = rating | [#23](https://github.com/julianzangl/NatureCheckpoint/issues/23) |

The Grafana dashboard JSON is exported into the repository, so it can be re-imported.

Check-in statistics never show individual visitor histories. Counts below a threshold are hidden.

## Analytics

([#25](https://github.com/julianzangl/NatureCheckpoint/issues/25))

Per station and day, the backend computes:

- average, median, min and max of each sensor value
- trend direction (rising / falling / stable)

The report is available via `GET /api/reports/daily` and shown in a dashboard.

## External data

([#26](https://github.com/julianzangl/NatureCheckpoint/issues/26))

| Source | Data | Use |
|---|---|---|
| [Euskalmet](https://opendata.euskadi.eus/catalogo/-/estaciones-meteorologicas-lecturas-recogidas-en-2026/) | Weather / UV | Shown next to local readings |
| [Open Data Euskadi: air quality](https://opendata.euskadi.eus/catalogo/-/calidad-aire-en-euskadi-2026/) | Air quality | Regional context |
| [Bilbao Open Data: Anillo Verde (GR 228)](https://www.bilbao.eus/opendata/es/catalogo/dato-anillo-verde) | Green ring route | Optional map overlay |

External data is fetched periodically and cached. If an API fails, the app keeps working. API keys live only in `.env`.

**Important:** check-ins only count NatureCheckpoint users, not all park visitors.
