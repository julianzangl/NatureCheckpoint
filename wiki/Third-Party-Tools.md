# Third-Party Tools

Tools chosen in [docs/architecture.md](https://github.com/julianzangl/NatureCheckpoint/blob/main/docs/architecture.md#2-decisions). Pinned versions are in `backend/requirements.txt`, `sensor-node/requirements*.txt` and `requirements-dev.txt`.

## Hardware

| Tool | Purpose | Link |
|---|---|---|
| grove.py | Grove Base HAT ADC (analogue sensors) and I2C modules | https://github.com/Seeed-Studio/grove.py |
| gpiozero (+ lgpio) | Digital GPIO on the Raspberry Pi 5 | https://gpiozero.readthedocs.io/ |

## Communication

| Tool | Purpose | Link |
|---|---|---|
| Eclipse Mosquitto 2 | Local MQTT broker | https://mosquitto.org/ |
| paho-mqtt 2.x | MQTT client in Python | https://pypi.org/project/paho-mqtt/ |
| mosquitto-clients | `mosquitto_pub` in `health.sh` | https://mosquitto.org/ |
| ngrok | Public HTTPS URL for the NFC tags | https://ngrok.com/ |

## Backend and web app

| Tool | Purpose | Link |
|---|---|---|
| FastAPI + Uvicorn | REST API, OpenAPI docs, web pages | https://fastapi.tiangolo.com/ |
| SQLModel (SQLite) | Stations, visitors, check-ins, vouchers | https://sqlmodel.tiangolo.com/ |
| Jinja2 | Server-rendered pages | https://jinja.palletsprojects.com/ |
| Pico.css | Minimal styling, no build step | https://picocss.com/ |
| Leaflet + OpenStreetMap | Checkpoint map | https://leafletjs.com/ |
| influxdb-client | Write and query InfluxDB | https://github.com/influxdata/influxdb-client-python |
| httpx | Calls to external APIs | https://www.python-httpx.org/ |

## Storage and visualisation

| Tool | Purpose | Link |
|---|---|---|
| InfluxDB 2.7 | Time-series storage | https://docs.influxdata.com/influxdb/v2/ |
| Grafana | Dashboards, provisioned from files | https://grafana.com/docs/grafana/latest/administration/provisioning/ |

## Deployment and quality

| Tool | Purpose | Link |
|---|---|---|
| Docker Compose | Run the server stack | https://docs.docker.com/compose/ |
| systemd | Sensor node service, health timer | - |
| ruff | Lint and format | https://docs.astral.sh/ruff/ |
| pytest | Tests | https://docs.pytest.org/ |
| GitHub Actions | CI on every pull request | https://docs.github.com/actions |

## Open data

| Source | Data | Link |
|---|---|---|
| Open-Meteo | Weather and UV forecast (no key) | https://open-meteo.com/ |
| Open Data Euskadi | Air quality (no key) | https://opendata.euskadi.eus/catalogo/-/calidad-aire-en-euskadi-2026/ |
| Bilbao Open Data | Anillo Verde (GR 228) route, optional map overlay | https://www.bilbao.eus/opendata/es/catalogo/dato-anillo-verde |

## Other

| Tool | Purpose |
|---|---|
| NFC Tools (mobile app) | Write and test NFC tags |
