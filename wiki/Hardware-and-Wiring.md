# Hardware and Wiring

The demo park has **two checkpoints**. Each one has the hardware below.

## Components

| Component | Interface | Purpose | Limitation | Issue |
|---|---|---|---|---|
| Raspberry Pi 5 | - | Runs the sensor node | Mains powered (USB-C) in the MVP | [#3](https://github.com/julianzangl/NatureCheckpoint/issues/3) |
| Grove Base HAT | I2C (ADC) | Grove ports and analogue inputs | - | [#3](https://github.com/julianzangl/NatureCheckpoint/issues/3) |
| Temperature & humidity sensor | Digital GPIO or I2C (module TBD) | Comfort rating | Must be shaded from direct sun | [#4](https://github.com/julianzangl/NatureCheckpoint/issues/4) |
| Light sensor | Analogue | Sun / shade context | Relative values only | [#5](https://github.com/julianzangl/NatureCheckpoint/issues/5) |
| LED bar or RGB LED | Digital GPIO | Shows walk rating and sensor faults | General information only | [#8](https://github.com/julianzangl/NatureCheckpoint/issues/8) |
| NFC device | TBD | Check-in | Static tags can be copied | [#9](https://github.com/julianzangl/NatureCheckpoint/issues/9) |
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
| Temperature & humidity | TBD (DHT11/DHT22 or DHT20) | D5, or I2C for DHT20 | Lab driver | ☐ | ☐ |
| Light | TBD | A0 | grove.py ADC | ☐ | ☐ |
| LED bar / RGB LED | TBD | D16 | gpiozero | ☐ | ☐ |
| LCD RGB backlight *(optional)* | TBD | I2C | grove.py | ☐ | ☐ |
| NFC device | TBD | TBD | TBD | ☐ | ☐ |

Add a photo or diagram of the wiring of each checkpoint here.

## Notes

- **GPIO library:** use `gpiozero` or the Grove library. `RPi.GPIO` does **not** work on the Raspberry Pi 5.
- **I2C:** enable it with `raspi-config` and check connected devices with `i2cdetect -y 1`.
- **Temperature sensor placement:** keep it out of direct sunlight, otherwise it reads too high.
- **Power:** the MVP runs indoors or at a supervised demo on mains power. Solar power and weatherproof enclosures are future work.
