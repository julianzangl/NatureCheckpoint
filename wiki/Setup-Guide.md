# Setup Guide

> **TBD.** Exact commands are added as the components are built ([#3](https://github.com/julianzangl/NatureCheckpoint/issues/3), [#10](https://github.com/julianzangl/NatureCheckpoint/issues/10), [#30](https://github.com/julianzangl/NatureCheckpoint/issues/30)). The server stack (section 1) is complete.
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

The stack runs Mosquitto, InfluxDB, Grafana, `mqtt-ingest` and the backend in Docker Compose. On Windows, run the commands in Git Bash or WSL.

1. Clone the repository:

   ```bash
   git clone https://github.com/julianzangl/NatureCheckpoint.git
   cd NatureCheckpoint
   ```

2. Copy `.env.example` to `.env` and fill in the values (see [Configuration](#configuration)). For the server stack you need at least:

   | Key | Value |
   |---|---|
   | `INFLUXDB_TOKEN` | A long random string, e.g. `openssl rand -hex 32` |
   | `INFLUXDB_ADMIN_PASSWORD` | Password for the InfluxDB web UI, min. 8 characters |
   | `INGEST_MQTT_PASSWORD` | Broker password of the `ingest` user |
   | `GRAFANA_ADMIN_PASSWORD` | Password for the Grafana web UI |

   InfluxDB reads the token and the admin password **only on the very first start**. To change them later, delete the volume (`docker compose -f deploy/docker-compose.yml down -v`, this deletes all stored readings).

3. Create the Mosquitto users. The broker rejects anonymous clients, so every device needs a user. The script writes `deploy/mosquitto/passwd` (git-ignored):

   ```bash
   bash deploy/mosquitto/add-user.sh ingest  "<INGEST_MQTT_PASSWORD>"
   bash deploy/mosquitto/add-user.sh station-1 "<password of checkpoint 1>"
   bash deploy/mosquitto/add-user.sh station-2 "<password of checkpoint 2>"
   ```

   On a sensor node, put its user and password into `MQTT_USERNAME` and `MQTT_PASSWORD`. If you add a user while the broker is running, reload it with `docker compose -f deploy/docker-compose.yml kill -s SIGHUP mosquitto`.

4. Start everything:

   ```bash
   docker compose -f deploy/docker-compose.yml up -d --build
   ```

5. Check that everything is running: `docker compose -f deploy/docker-compose.yml ps` lists all five services as `Up`, InfluxDB as `healthy`.

   | What | Where |
   |---|---|
   | API docs | http://localhost:8000/docs |
   | Grafana | http://localhost:3000 (user `admin`, `GRAFANA_ADMIN_PASSWORD`) |
   | InfluxDB | http://localhost:8086 (user `admin`, `INFLUXDB_ADMIN_PASSWORD`) |
   | MQTT broker | `localhost:1883` |

6. Send test data without a Pi. `tools/fake_station.py` publishes plausible readings and health data for `station-1` and `station-2` with the login from `MQTT_USERNAME` / `MQTT_PASSWORD` in `.env`:

   ```bash
   python tools/fake_station.py               # every 10 s until Ctrl+C
   python tools/fake_station.py --count 1     # one round
   python tools/fake_station.py --invalid     # also one broken message per round
   ```

   The data appears in InfluxDB (*Data Explorer*, bucket `environment`). Broken messages show up as warnings in `docker compose -f deploy/docker-compose.yml logs -f mqtt-ingest` and are skipped.

   Without Python, a single message also works with the broker image:

   ```bash
   docker compose -f deploy/docker-compose.yml exec mosquitto mosquitto_pub -u station-1 -P "<password>" -q 1 \
     -t naturecheckpoint/station-1/readings \
     -m '{"station_id":"station-1","timestamp":"2026-11-19T10:00:00Z","temperature":17.4,"humidity":62.0,"light":540,"condition":"good"}'
   ```

### How the ingest works

`mqtt-ingest` (`backend/ingest/`) subscribes to `naturecheckpoint/+/readings` and `naturecheckpoint/+/health` with QoS 1 and writes each message to InfluxDB (measurements `environment` and `device_health`, see [Data and Dashboards](Data-and-Dashboards)).

- A message is skipped with a warning if the JSON is invalid, a field is unknown, the `station_id` does not match the topic, the timestamp has no timezone, or a value has the wrong type.
- A sensor value of `null` means the sensor failed. The field is left out, the rest is stored.
- The ingest reconnects to the broker on its own. It uses a persistent session, so the broker keeps QoS 1 messages while the ingest restarts.
- If InfluxDB is down, the error is logged and the ingest keeps running.

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
| `MQTT_USERNAME`, `MQTT_PASSWORD` | Sensor node, `fake_station.py` | Broker login of the checkpoint (one user per device) |
| `INGEST_MQTT_USERNAME`, `INGEST_MQTT_PASSWORD` | Ingest | Broker login of `mqtt-ingest` (default user `ingest`) |
| `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET` | Ingest, backend, Grafana | Time-series database. The token becomes the admin token on the first start. |
| `INFLUXDB_ADMIN_PASSWORD` | InfluxDB | Password of the web UI user `admin` (first start only) |
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
| `Connection refused` / `not authorised` from the broker | The user is missing in `deploy/mosquitto/passwd` or the password differs. Run `bash deploy/mosquitto/add-user.sh` again and reload the broker. |
| A container exits with `set INFLUXDB_TOKEN in .env` (or similar) | The key is empty in `.env`. |
| No data in InfluxDB | `docker compose -f deploy/docker-compose.yml logs mqtt-ingest` shows skipped messages and connection errors. |
| Mosquitto warns that `passwd` is world readable | Harmless on Windows and macOS bind mounts. |
| Phone cannot open the check-in page | Use the ngrok URL, or put phone and Pi on the same hotspot |
