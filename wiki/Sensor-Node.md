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
  "condition": "good",
  "condition_reason": "all values in comfort range"
}
```

It is published on `naturecheckpoint/<station_id>/readings` (QoS 1) and appended to a local JSON-lines log. While the broker is unreachable, paho-mqtt queues messages in memory and sends them after reconnecting.

**Validation:** a value outside its plausible range is discarded (sent as `null`) and logged as a warning. The sample is still sent with the remaining values. The ranges are below.

| Value | Plausible range |
|---|---|
| Temperature | -20 to 50 °C |
| Humidity | 0 to 100 % |
| Light | sensor min to sensor max |

## Walk-condition rating

([#7](https://github.com/julianzangl/NatureCheckpoint/issues/7))

A pure function `rate(readings, thresholds)` in `nc_sensor/conditions.py` maps the latest readings to a tuple `(condition, reason)`: `good`, `fair`, `poor` or `fault`, plus a short reason. Both go into the MQTT payload as `condition` and `condition_reason`. The function has no hardware or clock access, so it is fully unit-tested (`sensor-node/tests/test_conditions.py`).

Thresholds are read from `sensor-node/config.toml` with `load_thresholds()`, not hard-coded. All ranges are inclusive:

```toml
[conditions.temperature]
unit = "°C"
good = [15.0, 25.0]   # inside: good
fair = [8.0, 30.0]    # inside, but not good: fair. Outside: poor
```

Current values (to be calibrated on site):

| Level | Temperature | Humidity |
|---|---|---|
| **good** | 15 to 25 °C | 30 to 70 % |
| **fair** | 8 to 15 °C or 25 to 30 °C | 20 to 30 % or 70 to 85 % |
| **poor** | below 8 °C or above 30 °C | below 20 % or above 85 % |

Examples:

| Readings | Result | Reason |
|---|---|---|
| 17.4 °C, 62 % | `good` | `all values in comfort range` |
| 28 °C, 90 % | `poor` | `humidity high (90 %)` |
| 20 °C, humidity failed | `good` | `all values in comfort range (humidity missing)` |
| both failed | `fault` | `no sensor values` |

The worst level of all sensors decides the result. Light adds context (sun / shade) but does not make the rating worse.

The rating is general information. It is **not** medical or safety advice.

## LED states

([#8](https://github.com/julianzangl/NatureCheckpoint/issues/8))

`nc_sensor/actuators/led.py`, class `StatusLed` with `show(condition)` and `off()`. The LED updates locally right after each rating, without waiting for the backend. Showing the same condition again leaves the LED untouched, so a blinking pattern does not restart.

The driver depends on the module in the kit. It is chosen in the `[led]` table of `sensor-node/config.toml` (pins are BCM GPIO numbers; a Grove port `Dn` carries GPIO `n`):

| `type` | Hardware | Library |
|---|---|---|
| `single` (default) | one LED on **D16** | `gpiozero.LED` |
| `traffic` | three LEDs: green, yellow, red | `gpiozero.LED` |
| `rgb` | one RGB LED (three pins) | `gpiozero.RGBLED` |
| `none` | no LED, only a log line (laptop) | - |

| State | `traffic` | `rgb` | `single` |
|---|---|---|---|
| good | green on | green | on |
| fair | yellow on | yellow | long on, short off (2 s / 0.5 s) |
| poor | red on | red | fast blinking (0.15 s) |
| sensor fault | yellow blinking (0.5 s) | white blinking (0.5 s) | blinking (0.5 s) |

`traffic` or `rgb` is easier to read for visitors; `single` is the fallback when the kit only has one LED.

Manual test on the Pi (cycles through all four states):

```bash
cd sensor-node
python -m nc_sensor.actuators.led --seconds 4
```

## Configuration

All settings come from `.env`. Full list: [Setup Guide](Setup-Guide#configuration).

| Key | Example | Meaning |
|---|---|---|
| `STATION_ID` | `station-1` | ID of this checkpoint |
| `SAMPLE_INTERVAL_S` | `10` | Seconds between samples |
| `MQTT_HOST` / `MQTT_PORT` | `localhost` / `1883` | Broker address |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | `station-1` / *secret* | Broker login of this checkpoint |

## Running as a service

([#30](https://github.com/julianzangl/NatureCheckpoint/issues/30)) **TBD**

- `systemd` units for the sensor loop and the health script start the programs on boot and restart them on failure.
- Logs are written to a file and rotated.
- An install script sets up a fresh Pi.

## Pi health reporting

([#29](https://github.com/julianzangl/NatureCheckpoint/issues/29)) **TBD**

A bash script `deploy/pi/health.sh` runs every 60 s via a `systemd` timer. It reads:

- CPU temperature (`/sys/class/thermal/thermal_zone0/temp`)
- Load (`/proc/loadavg`)
- Uptime (`/proc/uptime`)

It publishes them with `mosquitto_pub` on `naturecheckpoint/<station_id>/health`. The dashboard marks a station as offline when it stops reporting.
