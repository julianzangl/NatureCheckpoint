"""Status LED of a checkpoint: shows the walk condition and sensor faults on site.

The LED updates locally, without the backend. Which module the kit has decides the driver,
set in the `[led]` table of `sensor-node/config.toml`:

- `single`: one LED (`gpiozero.LED`). Levels are told apart by blinking speed.
- `traffic`: three LEDs, green / yellow / red (`gpiozero.LED` each).
- `rgb`: one RGB LED with three pins (`gpiozero.RGBLED`).
- `none`: no LED, only logging (laptop, CI).

Manual test on the Pi: ``python -m nc_sensor.actuators.led`` cycles through all states.
"""

from __future__ import annotations

import argparse
import logging
import time
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"

CONDITIONS = ("good", "fair", "poor", "fault")
FAULT_BLINK = (0.5, 0.5)

Rgb = tuple[float, float, float]
GREEN: Rgb = (0.0, 1.0, 0.0)
YELLOW: Rgb = (1.0, 0.6, 0.0)
RED: Rgb = (1.0, 0.0, 0.0)
WHITE: Rgb = (1.0, 1.0, 1.0)


@dataclass(frozen=True)
class Pattern:
    """What one light does: which colour or LED is lit, and whether it blinks.

    `blink` is `(on_time, off_time)` in seconds, or None for a steady light.
    """

    target: str | Rgb
    blink: tuple[float, float] | None = None


# One entry per driver kind and condition. Every condition has a distinct state,
# and a fault always blinks (#8).
PATTERNS: dict[str, dict[str, Pattern]] = {
    "single": {
        "good": Pattern("led"),
        "fair": Pattern("led", blink=(2.0, 0.5)),
        "poor": Pattern("led", blink=(0.15, 0.15)),
        "fault": Pattern("led", blink=FAULT_BLINK),
    },
    "traffic": {
        "good": Pattern("green"),
        "fair": Pattern("yellow"),
        "poor": Pattern("red"),
        # Like a traffic light that is out of service.
        "fault": Pattern("yellow", blink=FAULT_BLINK),
    },
    "rgb": {
        "good": Pattern(GREEN),
        "fair": Pattern(YELLOW),
        "poor": Pattern(RED),
        "fault": Pattern(WHITE, blink=FAULT_BLINK),
    },
}


def pattern_for(kind: str, condition: str) -> Pattern:
    """Pure mapping from a condition to the LED pattern. Unknown conditions count as fault."""
    patterns = PATTERNS[kind]
    return patterns.get(condition, patterns["fault"])


class Light(Protocol):
    """The subset of gpiozero's LED / RGBLED API that is used here."""

    def on(self) -> None: ...
    def off(self) -> None: ...
    def blink(self, on_time: float, off_time: float, **kwargs: Any) -> None: ...
    def close(self) -> None: ...


class StatusLed:
    """Shows a condition on the LED. Repeating the same condition keeps the LED as it is,
    so a blinking pattern does not restart (and flicker) on every sample."""

    def __init__(self, kind: str, lights: Mapping[str, Light]) -> None:
        if kind not in PATTERNS:
            raise ValueError(f"unknown LED type {kind!r}, expected one of {sorted(PATTERNS)}")
        self.kind = kind
        self.lights = dict(lights)
        self.current: str | None = None

    def show(self, condition: str) -> None:
        if condition == self.current:
            return
        if condition not in CONDITIONS:
            logger.warning("unknown condition %r, showing fault", condition)
        pattern = pattern_for(self.kind, condition)
        self._apply(pattern)
        self.current = condition
        logger.info("LED shows %s", condition)

    def off(self) -> None:
        for light in self.lights.values():
            light.off()
        self.current = None

    def close(self) -> None:
        self.off()
        for light in self.lights.values():
            light.close()

    def _apply(self, pattern: Pattern) -> None:
        if self.kind == "rgb":
            light = self.lights["rgb"]
            if pattern.blink:
                light.blink(*pattern.blink, on_color=pattern.target, background=True)
            else:
                light.color = pattern.target  # type: ignore[attr-defined]
            return

        for name, light in self.lights.items():
            if name != pattern.target:
                light.off()
        target = self.lights[pattern.target]  # type: ignore[index]
        if pattern.blink:
            target.blink(*pattern.blink, background=True)
        else:
            target.on()


class LogOnlyLed:
    """Stand-in when there is no LED (`type = "none"`), e.g. on a laptop."""

    current: str | None = None

    def show(self, condition: str) -> None:
        if condition != self.current:
            logger.info("LED (none) would show %s", condition)
            self.current = condition

    def off(self) -> None:
        self.current = None

    def close(self) -> None:
        self.off()


def create_status_led(
    config: Mapping[str, Any], gpio: Callable[[], Any] | None = None
) -> StatusLed | LogOnlyLed:
    """Build the LED from the `[led]` table of config.toml.

    `gpio` returns the gpiozero module; tests pass a fake. gpiozero is imported lazily
    because it only exists on the Pi (installed via apt).
    """
    kind = config.get("type", "single")
    if kind == "none":
        return LogOnlyLed()
    if kind not in PATTERNS:
        raise ValueError(f"unknown LED type {kind!r}, expected one of {sorted(PATTERNS)}")
    gpiozero = (gpio or _import_gpiozero)()

    pins = config.get("pins", {})
    if kind == "single":
        return StatusLed(kind, {"led": gpiozero.LED(_pin(pins, "led"))})
    if kind == "traffic":
        names = ("green", "yellow", "red")
        return StatusLed(kind, {name: gpiozero.LED(_pin(pins, name)) for name in names})
    rgb = gpiozero.RGBLED(
        _pin(pins, "red"),
        _pin(pins, "green"),
        _pin(pins, "blue"),
        active_high=config.get("active_high", True),
    )
    return StatusLed(kind, {"rgb": rgb})


def load_led_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open("rb") as file:
        return tomllib.load(file).get("led", {"type": "none"})


def _pin(pins: Mapping[str, Any], name: str) -> int:
    pin = pins.get(name)
    if not isinstance(pin, int) or isinstance(pin, bool):
        raise ValueError(f"[led.pins] needs a GPIO number for {name!r}, got {pin!r}")
    return pin


def _import_gpiozero() -> Any:
    import gpiozero

    return gpiozero


def main() -> None:
    parser = argparse.ArgumentParser(description="Cycle the status LED through all states.")
    parser.add_argument("--seconds", type=float, default=4, help="time per state")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    led = create_status_led(load_led_config())
    try:
        for condition in CONDITIONS:
            print(f"-> {condition}")
            led.show(condition)
            time.sleep(args.seconds)
    finally:
        led.close()


if __name__ == "__main__":
    main()
