# Hardware and Wiring

The demo park has **two checkpoints**. Each one has the hardware below.

## Components

| Component | Interface | Purpose | Limitation | Issue |
|---|---|---|---|---|
| Raspberry Pi 5 | - | Runs the sensor node | Mains powered (USB-C) in the MVP | [#3](https://github.com/julianzangl/NatureCheckpoint/issues/3) |
| Grove Base HAT | I2C (ADC) | Grove ports and analogue inputs | - | [#3](https://github.com/julianzangl/NatureCheckpoint/issues/3) |
| Temperature & humidity sensor | Digital GPIO (Grove DHT11) | Comfort rating | Must be shaded from direct sun | [#4](https://github.com/julianzangl/NatureCheckpoint/issues/4) |
| Light sensor | Analogue | Sun / shade context | Relative values only | [#5](https://github.com/julianzangl/NatureCheckpoint/issues/5) |
| LED bar or RGB LED | Digital GPIO | Shows walk rating and sensor faults | General information only | [#8](https://github.com/julianzangl/NatureCheckpoint/issues/8) |
| NFC reader (M5Stack Unit RFID 2) | I2C | Check-in | Reads 13.56 MHz cards and tags; iPhones cannot be read like a card | [#9](https://github.com/julianzangl/NatureCheckpoint/issues/9) |
| Barometer *(planned)* | I2C | Pressure trend | Not a weather forecast | [#27](https://github.com/julianzangl/NatureCheckpoint/issues/27) |
| Sound level sensor *(planned)* | Analogue | Relative noise level | Never records audio | [#27](https://github.com/julianzangl/NatureCheckpoint/issues/27) |
| UV sensor *(planned)* | Analogue | UV indication | Not an official UV alert | [#27](https://github.com/julianzangl/NatureCheckpoint/issues/27) |

The set covers the three sensor types required by the course:

- **Digital GPIO**
- **Analogue** (via the HAT ADC)
- **I2C**

## Connections

> **TBD.** Fill in the exact models once wired. The ports below are the defaults from [docs/architecture.md](https://github.com/julianzangl/NatureCheckpoint/blob/main/docs/architecture.md#6-hardware-defaults). Change them here if your kit differs.

| Component | Exact model | Default Grove port | Library | Checkpoint 1 | Checkpoint 2 |
|---|---|---|---|---|---|
| Temperature & humidity | Grove Temperature & Humidity Sensor (DHT11) | **D18** (data on GPIO18, GPIO19 unused) | grove.py DHT driver (lab driver) | ☐ | ☐ |
| Light | TBD | A0 | grove.py ADC | ☐ | ☐ |
| LED bar / RGB LED | TBD | D16 | gpiozero | ☐ | ☐ |
| LCD 16x2 | Grove 16x2 LCD, white on blue (`0x3E`) | **I2C** (bus 1) | grove.py | ☑ | ☐ |
| NFC reader 1 | M5Stack Unit RFID 2, WS1850S (`0x28`) | **I2C** (bus 1) | RC522-compatible, over I2C | ☑ | - |
| NFC reader 2 | M5Stack Unit RFID 2, WS1850S (`0x28`) | **D22** (software I2C, bus 3) | RC522-compatible, over I2C | - | ☑ |

Add a photo or diagram of the wiring of each checkpoint here.

## Temperature and humidity sensor

([#4](https://github.com/julianzangl/NatureCheckpoint/issues/4))

| Item | Value |
|---|---|
| Model | Grove Temperature & Humidity Sensor, DHT11 (single-wire digital) |
| Grove port | **D18** on the Base HAT. The socket carries GPIO18 and GPIO19; the DHT data line is GPIO18. |
| Code | `sensor-node/nc_sensor/sensors/temp_humidity.py`, class `TempHumiditySensor` |
| Driver | `grove.grove_temperature_humidity_sensor.DHT` from grove.py (same as in the labs) |
| Range accepted | -20 to 50 °C, 0 to 100 % (other values are dropped as implausible) |

`TempHumiditySensor().read()` returns `{"temperature": float | None, "humidity": float | None}` in °C and %. A failed read is retried 3 times with 2 s between tries (the DHT11 needs at least 1 s between reads). After that both values are `None`; the sensor never raises into the main loop.

Manual test on the Pi, inside the project venv:

```bash
cd sensor-node
python -m nc_sensor.sensors.temp_humidity            # DHT11 on D18, prints every 2 s
python -m nc_sensor.sensors.temp_humidity --type 22  # if a DHT22 is fitted instead
```

If DHT reads turn out unreliable on the Pi 5, the fallback is a DHT20 on an I2C port (address `0x38`, check with `i2cdetect -y 1`).

## Notes

- **GPIO library:** use `gpiozero` or the Grove library. `RPi.GPIO` does **not** work on the Raspberry Pi 5.
- **I2C:** enable it with `raspi-config` and check connected devices with `i2cdetect -y 1`.
- **Temperature sensor placement:** keep it out of direct sunlight, otherwise it reads too high.
- **Power:** the MVP runs indoors or at a supervised demo on mains power. Solar power and weatherproof enclosures are future work.

## NFC readers

([#9](https://github.com/julianzangl/NatureCheckpoint/issues/9))

For the demo, one Pi carries both readers: reader 1 stands for checkpoint 1 (`station-1`), reader 2 for checkpoint 2 (`station-2`).

| Item | Reader 1 | Reader 2 |
|---|---|---|
| Model | M5Stack Unit RFID 2 (WS1850S, RC522-compatible) | same |
| Grove port | any `I2C` port of the Base HAT | **D22** |
| Linux bus | `/dev/i2c-1` | `/dev/i2c-3` (software I2C) |
| Address | `0x28` | `0x28` |
| Power | 3.3 V from the HAT port | 3.3 V from the HAT port |

**Why a second bus:** the address `0x28` is fixed, and all three `I2C` ports of the HAT are the same bus. Two readers on that bus would collide. An I2C hub does not help, because it only shares the one bus.

**Pi setting** (already done on the Pi, needs a reboot after a change). Last line of `/boot/firmware/config.txt`, in the `[all]` section:

```text
dtoverlay=i2c-gpio,bus=3,i2c_gpio_sda=23,i2c_gpio_scl=22
```

On Grove ports the first pin (yellow wire position) is **SCL**. On D22 that pin is GPIO22, so GPIO22 = SCL and GPIO23 = SDA. With the two swapped, bus 3 exists but stays empty. The original file is kept as `/boot/firmware/config.txt.bak-i2c3`.

**Check** (`i2cdetect` and `i2cget` are in `/usr/sbin`, which is not on the PATH of a plain SSH command):

```bash
/usr/sbin/i2cdetect -y 1       # 08 = HAT ADC, 28 = reader 1, 3e = LCD
/usr/sbin/i2cdetect -y 3       # 28 = reader 2
/usr/sbin/i2cget -y 1 0x28 0x37   # version register, 0x15 on both readers
/usr/sbin/i2cget -y 3 0x28 0x37
```

Both readers were detected and returned version `0x15` on 26 Nov 2026. Reading a card from Python is still open.

**Limitations:** the readers read cards, key fobs and NTAG stickers. They cannot open a URL on a phone, and iPhones cannot be read like a card.
