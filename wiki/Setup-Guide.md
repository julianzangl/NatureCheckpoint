# Setup Guide

> **TBD.** Exact commands are added as the components are built ([#3](https://github.com/julianzangl/NatureCheckpoint/issues/3), [#10](https://github.com/julianzangl/NatureCheckpoint/issues/10), [#11](https://github.com/julianzangl/NatureCheckpoint/issues/11), [#30](https://github.com/julianzangl/NatureCheckpoint/issues/30)).
>
> **Goal:** a new person can reproduce the system by following this page alone.

## Requirements

| What | Version / note |
|---|---|
| Raspberry Pi 5 | Raspberry Pi OS (64-bit), one per checkpoint |
| Grove Base HAT + sensors | See [Hardware and Wiring](Hardware-and-Wiring) |
| Python | 3.11+ |
| Docker + Docker Compose | For backend, InfluxDB, Grafana, Mosquitto |
| Phone with NFC | Android and iPhone for testing |

## 1. Prepare the Raspberry Pi

1. Flash Raspberry Pi OS and enable SSH.
2. Enable I2C: `sudo raspi-config` → *Interface Options* → *I2C*.
3. Clone the repository:

   ```bash
   git clone https://github.com/julianzangl/NatureCheckpoint.git
   cd NatureCheckpoint/sensor-node
   ```

4. Create a virtual environment and install the dependencies: **TBD** (`requirements.txt`).
5. Check that the sensors are detected: `i2cdetect -y 1`.

## 2. Start backend and databases

**TBD** (`deploy/docker-compose.yml`). This starts:

- the backend
- InfluxDB
- Grafana
- Mosquitto

## 3. Start the sensor node

**TBD.** Covers:

- a manual start for testing
- installing the `systemd` services for permanent operation

## 4. Set up the NFC devices

**TBD**, depends on the hardware ([#9](https://github.com/julianzangl/NatureCheckpoint/issues/9)).

## Configuration

All configuration lives in `.env`, created from `.env.example`. **Never commit `.env`.** The repository is public.

| Key | Used by | Meaning |
|---|---|---|
| `STATION_ID` | Sensor node | ID of the checkpoint (`station-1`, `station-2`) |
| `SAMPLE_INTERVAL_S` | Sensor node | Seconds between samples |
| `MQTT_HOST`, `MQTT_PORT` | Sensor node, backend | Broker address |
| `DEVICE_API_KEY` | Sensor node, backend | Authenticates checkpoints |
| `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET` | Backend, Grafana | Time-series database |
| `DATABASE_PATH` | Backend | SQLite file |
| `EUSKALMET_API_KEY` | Backend | External weather data |

## Troubleshooting

| Problem | Check |
|---|---|
| Sensor not found | Wiring, port, `i2cdetect -y 1` |
| GPIO errors on Pi 5 | Use `gpiozero` / Grove library, not `RPi.GPIO` |
| No MQTT data at university | Campus blocks outbound MQTT. Use the local broker. |
