# Sensor Node

Python code that runs on the Raspberry Pi of each checkpoint (`sensor-node/` in the repository).

## Responsibilities

1. Read all sensors at a fixed interval.
2. Validate the values and drop missing or out-of-range ones.
3. Rate the walk conditions as **good / fair / poor**.
4. Show the rating, or a sensor fault, on the LED.
5. Publish readings and Pi health data via MQTT.
6. Write a local log.

## Sampling loop

([#6](https://github.com/julianzangl/NatureCheckpoint/issues/6))

Each valid sample is a JSON object:

```json
{
  "station_id": "station-1",
  "timestamp": "2026-11-10T14:30:00Z",
  "temperature": 17.4,
  "humidity": 62.0,
  "light": 540,
  "condition": "good"
}
```

**Validation:** a value outside its plausible range is discarded and logged as a warning. The sample is still sent with the remaining values. The ranges are below.

| Value | Plausible range |
|---|---|
| Temperature | -20 to 50 °C |
| Humidity | 0 to 100 % |
| Light | sensor min to sensor max |

## Walk-condition rating

([#7](https://github.com/julianzangl/NatureCheckpoint/issues/7))

A pure function maps the latest readings to `good`, `fair` or `poor` and returns the reason. Thresholds are read from a config file, not hard-coded.

Initial proposal (to be calibrated):

| Level | Temperature | Humidity |
|---|---|---|
| **good** | 15 to 25 °C | 30 to 70 % |
| **fair** | 8 to 15 °C or 25 to 30 °C | 20 to 30 % or 70 to 85 % |
| **poor** | below 8 °C or above 30 °C | below 20 % or above 85 % |

The worst level of all sensors decides the result. Light adds context (sun / shade) but does not make the rating worse.

The rating is general information. It is **not** medical or safety advice.

## LED states

([#8](https://github.com/julianzangl/NatureCheckpoint/issues/8))

| State | LED |
|---|---|
| good | green / full bar (TBD) |
| fair | yellow / half bar (TBD) |
| poor | red / low bar (TBD) |
| sensor fault | blinking (TBD) |

The LED updates locally, without waiting for the backend.

## Configuration

All settings come from `.env`. Full list: [Setup Guide](Setup-Guide#configuration).

| Key | Example | Meaning |
|---|---|---|
| `STATION_ID` | `station-1` | ID of this checkpoint |
| `SAMPLE_INTERVAL_S` | `30` | Seconds between samples |
| `MQTT_HOST` / `MQTT_PORT` | `localhost` / `1883` | Broker address |

## Running as a service

([#30](https://github.com/julianzangl/NatureCheckpoint/issues/30)) **TBD**

- `systemd` units for the sensor loop and the health script start the programs on boot and restart them on failure.
- Logs are written to a file and rotated.
- An install script sets up a fresh Pi.

## Pi health reporting

([#29](https://github.com/julianzangl/NatureCheckpoint/issues/29)) **TBD**

The checkpoint periodically publishes:

- CPU temperature
- Load
- Uptime

on `naturecheckpoint/<station_id>/health`. The dashboard marks a station as offline when it stops reporting.
