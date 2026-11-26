# Sensor Node

Python code that runs on the Raspberry Pi of each checkpoint (`sensor-node/` in the repository).

## Responsibilities

1. Read all sensors at a fixed interval.
2. Validate the values and drop missing or out-of-range ones.
3. Rate the walk conditions as **good / fair / poor**.
4. Show the rating, or a sensor fault, on the LED and the LCD.
5. Publish readings and Pi health data via MQTT.
6. Write a local log.
7. Read tapped NFC cards and send the check-in to the backend.

## Sampling loop

([#6](https://github.com/julianzangl/NatureCheckpoint/issues/6), [#12](https://github.com/julianzangl/NatureCheckpoint/issues/12))

`python -m nc_sensor.main` (in `sensor-node/`, project venv) runs the checkpoint:

- Every `SAMPLE_INTERVAL_S` it reads the DHT11 and the light sensor, rates the conditions (`conditions.py`), updates the LED and the LCD, and publishes one message per station ID (`STATION_ID`, plus `STATION_IDS` in the demo) on `naturecheckpoint/<station_id>/readings` with QoS 1 (`publisher.py`).
- Each sample is also appended to `data/readings.jsonl` (rotated at 5 MB, 3 files), so the data survives a broker outage.
- paho reconnects on its own and keeps up to 1000 QoS 1 messages while the broker is away.
- A broken sensor is sent as `null`; a missing LED or LCD is logged and the node keeps running.
- `python -m nc_sensor.main --once` takes one sample and exits (quick test).

The DHT11 is read with our own lgpio driver (`sensors/dht_lgpio.py`). grove.py has no DHT11 module, and RPi.GPIO-based drivers miss edges on the Pi 5.

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
| Light | 0 to 1000 (relative, see [Hardware and Wiring](Hardware-and-Wiring#light-sensor)) |

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
| `STATION_IDS` | `station-2` | Demo: further station IDs this Pi publishes for |
| `BACKEND_URL` | `http://localhost:8000` | Backend for card check-ins |
| `DEVICE_TOKEN` | *secret* | Must match the backend's `DEVICE_TOKEN` |
| `CARD_SALT` | *secret* | Salt for hashing card UIDs |

## NFC card check-in and LCD

([#9](https://github.com/julianzangl/NatureCheckpoint/issues/9), [#16](https://github.com/julianzangl/NatureCheckpoint/issues/16))

A second thread polls the readers from `[nfc] readers` in `config.toml` (reader 1 on I2C bus 1 = `station-1`, reader 2 on bus 3 = `station-2`) every 0.1 s:

1. `sensors/nfc.py` reads the card UID (ISO 14443A: REQA, anticollision, select, halt). A card held on the reader counts once; the same card is ignored for 3 s.
2. `checkin.py` hashes the UID with `CARD_SALT` (SHA-256, 32 hex characters) and sends `POST /api/checkins/card` with `Authorization: Bearer <DEVICE_TOKEN>` to `BACKEND_URL`. The raw UID never leaves the Pi.
3. The LCD shows the result for 5 s, then the conditions again:

| Situation | LCD |
|---|---|
| Idle | `Walk: GOOD` / `23C 42% Tap card` |
| New stamp | `Stamp! 3/6` / station name |
| Same station again today | `Already 3/6` / `Come back tmrw` |
| Goal reached | `Voucher! 6/6` / `NC-XXXXXXXX` |
| Backend down | `Check-in failed` / `Server offline` |

Manual reader test: `python -m nc_sensor.sensors.nfc --bus 1` prints each tapped UID.

## Running as a service

([#30](https://github.com/julianzangl/NatureCheckpoint/issues/30))

`deploy/pi/` contains the `systemd` units. `sudo deploy/pi/install-services.sh` fills in the repository path and user, installs and starts them:

| Unit | Runs |
|---|---|
| `nc-sensor-node.service` | `python -m nc_sensor.main` (restarts always) |
| `nc-backend.service` | backend on port 8000 |
| `nc-ingest.service` | MQTT → InfluxDB ingest |
| `nc-health.timer` → `nc-health.service` | `deploy/pi/health.sh` every 60 s |

Logs: `journalctl -u nc-sensor-node -f`. With `--stop-lab5` the script also stops the course's `lab5-publisher.service`, which uses GPIO16 too.

## Pi health reporting

([#29](https://github.com/julianzangl/NatureCheckpoint/issues/29))

A bash script `deploy/pi/health.sh` runs every 60 s via a `systemd` timer. It reads:

- CPU temperature (`/sys/class/thermal/thermal_zone0/temp`)
- Load (`/proc/loadavg`)
- Uptime (`/proc/uptime`)

It publishes them with `mosquitto_pub` on `naturecheckpoint/<station_id>/health`. The dashboard marks a station as offline when it stops reporting.
