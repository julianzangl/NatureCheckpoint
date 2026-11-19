# Setup Guide

> **TBD.** Exact commands are added as the components are built ([#3](https://github.com/julianzangl/NatureCheckpoint/issues/3), [#10](https://github.com/julianzangl/NatureCheckpoint/issues/10), [#11](https://github.com/julianzangl/NatureCheckpoint/issues/11), [#30](https://github.com/julianzangl/NatureCheckpoint/issues/30)).
>
> **Goal:** a new person can reproduce the system by following this page alone.

## Requirements

| What | Version / note |
|---|---|
| Raspberry Pi 5 | Raspberry Pi OS 64-bit (Debian 13 trixie) |
| Grove Base HAT + sensors | See [Hardware and Wiring](Hardware-and-Wiring) |
| Python | 3.11+ (we use 3.13) |
| Docker + Docker Compose | Runs Mosquitto, `mqtt-ingest`, backend, InfluxDB, Grafana |
| ngrok account | Free static domain for the NFC URL |
| Phone with NFC | Android and iPhone for testing |

## 1. Server stack (laptop or Pi)

1. Clone the repository:

   ```bash
   git clone https://github.com/julianzangl/NatureCheckpoint.git
   cd NatureCheckpoint
   ```

2. Copy `.env.example` to `.env` and fill in the values (see [Configuration](#configuration)).
3. Create the Mosquitto users: **TBD**, script in `deploy/mosquitto/` ([#11](https://github.com/julianzangl/NatureCheckpoint/issues/11)).
4. Start everything:

   ```bash
   docker compose -f deploy/docker-compose.yml up -d
   ```

5. Check that everything is running:

| What | Where |
|---|---|
| API docs | http://localhost:8000/docs |
| Grafana | http://localhost:3000 |
| InfluxDB | http://localhost:8086 |

## 2. Raspberry Pi (sensor node)

1. Flash Raspberry Pi OS and enable SSH.
2. Enable I2C: `sudo raspi-config` → *Interface Options* → *I2C*.
3. Install the system packages: `sudo apt install python3-gpiozero python3-lgpio mosquitto-clients i2c-tools`.
4. Create the virtual environment with access to those packages:

   ```bash
   cd NatureCheckpoint/sensor-node
   python3 -m venv --system-site-packages .venv
   source .venv/bin/activate
   pip install -r requirements-pi.txt
   ```

5. Check that the sensors are detected: `i2cdetect -y 1`.
6. Start it manually for a test: **TBD** ([#6](https://github.com/julianzangl/NatureCheckpoint/issues/6)).
7. Install the `systemd` services: **TBD**, `deploy/pi/install.sh` ([#30](https://github.com/julianzangl/NatureCheckpoint/issues/30)).

## 3. Public URL and NFC

1. Reserve the free static domain in the ngrok dashboard.
2. Set `NGROK_AUTHTOKEN` and `PUBLIC_BASE_URL` in `.env`.
3. Write `https://<PUBLIC_BASE_URL>/c/station-1` and `https://<PUBLIC_BASE_URL>/c/station-2` to the NFC tags, e.g. with the *NFC Tools* app. If the NFC devices turn out to be reader modules: **TBD** ([#9](https://github.com/julianzangl/NatureCheckpoint/issues/9)).

## Configuration

All configuration lives in `.env`, created from `.env.example`. **Never commit `.env`.** The repository is public.

| Key | Used by | Meaning |
|---|---|---|
| `STATION_ID` | Sensor node | `station-1` or `station-2` |
| `SAMPLE_INTERVAL_S` | Sensor node | Seconds between samples (default 10) |
| `MQTT_HOST`, `MQTT_PORT` | Sensor node, ingest | Broker address |
| `MQTT_USERNAME`, `MQTT_PASSWORD` | Sensor node, ingest | Broker login (one user per device) |
| `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET` | Ingest, backend, Grafana | Time-series database |
| `DATABASE_PATH` | Backend | SQLite file |
| `PUBLIC_BASE_URL` | Backend, NFC tags | Public HTTPS URL |
| `NGROK_AUTHTOKEN` | ngrok | ngrok login |
| `GRAFANA_ADMIN_PASSWORD` | Grafana | Admin login |

Walk-condition thresholds are not secrets. They are versioned in `sensor-node/config.toml`.

## Troubleshooting

| Problem | Check |
|---|---|
| Sensor not found | Wiring, port, `i2cdetect -y 1` |
| GPIO errors on Pi 5 | Use `gpiozero`, not `RPi.GPIO`. Was the venv created with `--system-site-packages`? |
| No MQTT data at university | Campus blocks outbound MQTT. Use the local broker. |
| Phone cannot open the check-in page | Use the ngrok URL, or put phone and Pi on the same hotspot |
