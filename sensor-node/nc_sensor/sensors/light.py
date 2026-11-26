"""Grove light sensor (photoresistor) on an analogue port of the Grove Base HAT.

The HAT's ADC is read over I2C with grove.py. The value is the ADC reading relative to the
supply voltage, 0 (dark) to 1000 (full scale), so it does not depend on the ADC resolution.
It is a relative brightness, not lux.

Manual test on the Pi: ``python -m nc_sensor.sensors.light`` prints a reading every 2 s.
"""

from __future__ import annotations

import argparse
import logging
import math
import time
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, TypedDict

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"

# Grove Base HAT port A2 carries ADC channels 2 and 3; the sensor signal is on the first one.
DEFAULT_CHANNEL = 2
ADC_ADDRESS = 0x08
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY_S = 0.2

LIGHT_RANGE = (0.0, 1000.0)

DARK, SHADE, SUN = "dark", "shade", "sun"


class Reading(TypedDict):
    light: float | None


class Adc(Protocol):
    def read(self, channel: int) -> float:
        """Return the reading of ``channel`` as 0..1000 of full scale, like grove.py's ADC."""
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


def classify(light: float | None, dark_below: float, sun_above: float) -> str | None:
    """Map a light value to ``dark`` / ``shade`` / ``sun``; ``None`` if there is no value."""
    if light is None:
        return None
    if light < dark_below:
        return DARK
    if light > sun_above:
        return SUN
    return SHADE


def load_light_thresholds(path: Path = CONFIG_PATH) -> tuple[float, float]:
    """Read ``(dark_below, sun_above)`` from the ``[light]`` table of config.toml."""
    with path.open("rb") as file:
        table = tomllib.load(file).get("light")
    if not isinstance(table, dict):
        raise ValueError("config has no [light] table")
    try:
        dark_below = float(table["dark_below"])
        sun_above = float(table["sun_above"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("[light] needs numeric dark_below and sun_above") from exc
    if not LIGHT_RANGE[0] <= dark_below < sun_above <= LIGHT_RANGE[1]:
        raise ValueError("[light] needs 0 <= dark_below < sun_above <= 1000")
    return dark_below, sun_above


def _grove_adc() -> Adc:
    # Imported lazily: grove.py only exists on the Pi (requirements-pi.txt), not in CI.
    from grove.adc import ADC

    # Newer Base HATs (MM32 chip) answer at 0x08; grove.py still defaults to the old 0x04.
    return ADC(address=ADC_ADDRESS)


class LightSensor:
    """Reads the relative brightness (0..1000) and never raises on read errors."""

    def __init__(
        self,
        channel: int = DEFAULT_CHANNEL,
        retries: int = DEFAULT_RETRIES,
        retry_delay_s: float = DEFAULT_RETRY_DELAY_S,
        adc_factory: Callable[[], Adc] = _grove_adc,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.channel = channel
        self.retries = max(1, retries)
        self.retry_delay_s = retry_delay_s
        self._adc_factory = adc_factory
        self._sleep = sleep
        self._adc: Adc | None = None

    def read(self) -> Reading:
        for attempt in range(1, self.retries + 1):
            try:
                if self._adc is None:
                    self._adc = self._adc_factory()
                raw = self._adc.read(self.channel)
            # Catch everything: a sensor fault must never stop the main loop.
            except Exception as exc:
                # Drop the ADC so the next try reconnects after an I2C error.
                self._adc = None
                logger.warning(
                    "Light on A%d: read %d/%d failed: %s",
                    self.channel,
                    attempt,
                    self.retries,
                    exc,
                )
            else:
                light = validate(raw, *LIGHT_RANGE)
                if light is not None:
                    return {"light": light}
                logger.warning(
                    "Light on A%d: read %d/%d implausible: %r",
                    self.channel,
                    attempt,
                    self.retries,
                    raw,
                )
            if attempt < self.retries:
                self._sleep(self.retry_delay_s)
        logger.error("Light on A%d: no valid reading after %d tries", self.channel, self.retries)
        return {"light": None}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Print the light value every 2 s.")
    parser.add_argument("--channel", type=int, default=DEFAULT_CHANNEL, help="ADC channel (An)")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between reads")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        dark_below, sun_above = load_light_thresholds()
    except (OSError, ValueError) as exc:
        logger.warning("No light thresholds, printing raw values only: %s", exc)
        dark_below = sun_above = None

    sensor = LightSensor(channel=args.channel)
    print(f"Reading light sensor on Grove A{args.channel}. Ctrl+C to stop.")
    try:
        while True:
            light = sensor.read()["light"]
            if light is None:
                print("light: n/a", flush=True)
            elif dark_below is None or sun_above is None:
                print(f"light: {light:.0f} / 1000", flush=True)
            else:
                level = classify(light, dark_below, sun_above)
                print(f"light: {light:.0f} / 1000   ({level})", flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
