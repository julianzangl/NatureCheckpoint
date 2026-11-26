"""Grove temperature and humidity sensor (DHT11/DHT22) on a digital Grove port.

Manual test on the Pi: ``python -m nc_sensor.sensors.temp_humidity`` prints a reading every 2 s.
"""

from __future__ import annotations

import argparse
import logging
import math
import time
from collections.abc import Callable
from typing import Protocol, TypedDict

logger = logging.getLogger(__name__)

# Grove Base HAT port D18 carries GPIO18 and GPIO19; the DHT data line is the first one.
DEFAULT_PIN = 18
DEFAULT_DHT_TYPE = "11"
DEFAULT_RETRIES = 3
# The DHT11 needs at least 1 s between reads, the DHT22 2 s.
DEFAULT_RETRY_DELAY_S = 2.0

TEMPERATURE_RANGE_C = (-20.0, 50.0)
HUMIDITY_RANGE_PCT = (0.0, 100.0)


class Reading(TypedDict):
    temperature: float | None
    humidity: float | None


class DhtDriver(Protocol):
    def read(self) -> tuple[float | None, float | None]:
        """Return ``(humidity, temperature)`` like the grove.py DHT driver."""
        ...


def validate(value: float | None, lo: float, hi: float) -> float | None:
    """Return ``value`` as float if it lies within ``[lo, hi]``, otherwise ``None``."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or not lo <= number <= hi:
        return None
    return number


def _lgpio_dht_driver(dht_type: str, pin: int) -> DhtDriver:
    # Imported lazily: lgpio only exists on the Pi, not in CI.
    from nc_sensor.sensors.dht_lgpio import LgpioDht

    return LgpioDht(dht_type, pin)


class TempHumiditySensor:
    """Reads temperature (°C) and relative humidity (%) and never raises on read errors."""

    def __init__(
        self,
        pin: int = DEFAULT_PIN,
        dht_type: str = DEFAULT_DHT_TYPE,
        retries: int = DEFAULT_RETRIES,
        retry_delay_s: float = DEFAULT_RETRY_DELAY_S,
        driver_factory: Callable[[str, int], DhtDriver] = _lgpio_dht_driver,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.pin = pin
        self.dht_type = dht_type
        self.retries = max(1, retries)
        self.retry_delay_s = retry_delay_s
        self._driver_factory = driver_factory
        self._sleep = sleep
        self._driver: DhtDriver | None = None

    def read(self) -> Reading:
        for attempt in range(1, self.retries + 1):
            try:
                if self._driver is None:
                    self._driver = self._driver_factory(self.dht_type, self.pin)
                humidity, temperature = self._driver.read()
            # Catch everything: a sensor fault must never stop the main loop.
            except Exception as exc:
                logger.warning(
                    "DHT%s on GPIO%d: read %d/%d failed: %s",
                    self.dht_type,
                    self.pin,
                    attempt,
                    self.retries,
                    exc,
                )
            else:
                reading: Reading = {
                    "temperature": validate(temperature, *TEMPERATURE_RANGE_C),
                    "humidity": validate(humidity, *HUMIDITY_RANGE_PCT),
                }
                if reading["temperature"] is not None or reading["humidity"] is not None:
                    if None in reading.values():
                        logger.warning(
                            "DHT%s: discarded implausible value (temperature=%r, humidity=%r)",
                            self.dht_type,
                            temperature,
                            humidity,
                        )
                    return reading
                logger.warning(
                    "DHT%s on GPIO%d: read %d/%d implausible (temperature=%r, humidity=%r)",
                    self.dht_type,
                    self.pin,
                    attempt,
                    self.retries,
                    temperature,
                    humidity,
                )
            if attempt < self.retries:
                self._sleep(self.retry_delay_s)
        logger.error(
            "DHT%s on GPIO%d: no valid reading after %d tries",
            self.dht_type,
            self.pin,
            self.retries,
        )
        return {"temperature": None, "humidity": None}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Print temperature and humidity every 2 s.")
    parser.add_argument("--pin", type=int, default=DEFAULT_PIN, help="BCM GPIO of the data line")
    parser.add_argument("--type", dest="dht_type", default=DEFAULT_DHT_TYPE, choices=["11", "22"])
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between reads")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sensor = TempHumiditySensor(pin=args.pin, dht_type=args.dht_type)
    print(f"Reading DHT{args.dht_type} on GPIO{args.pin} (Grove D{args.pin}). Ctrl+C to stop.")
    try:
        while True:
            reading = sensor.read()
            temperature, humidity = reading["temperature"], reading["humidity"]
            t = "n/a" if temperature is None else f"{temperature:.1f} °C"
            h = "n/a" if humidity is None else f"{humidity:.1f} %"
            print(f"temperature: {t}   humidity: {h}", flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
