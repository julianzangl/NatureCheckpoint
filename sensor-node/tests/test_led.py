from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from nc_sensor.actuators.led import (
    CONDITIONS,
    PATTERNS,
    LogOnlyLed,
    StatusLed,
    create_status_led,
    load_led_config,
    pattern_for,
)


class FakeLight:
    """Records calls like a gpiozero LED / RGBLED without touching hardware."""

    def __init__(self, *pins: int, **kwargs: Any) -> None:
        self.pins = pins
        self.kwargs = kwargs
        self.state = "off"
        self.color: tuple[float, float, float] | None = None
        self.blink_args: tuple[Any, ...] | None = None
        self.blink_kwargs: dict[str, Any] = {}
        self.calls = 0
        self.closed = False

    def on(self) -> None:
        self.state = "on"
        self.calls += 1

    def off(self) -> None:
        self.state = "off"
        self.color = None
        self.calls += 1

    def blink(self, *args: Any, **kwargs: Any) -> None:
        self.state = "blink"
        self.blink_args = args
        self.blink_kwargs = kwargs
        self.calls += 1

    def close(self) -> None:
        self.closed = True


def fake_gpiozero() -> SimpleNamespace:
    return SimpleNamespace(LED=FakeLight, RGBLED=FakeLight)


def traffic() -> tuple[StatusLed, dict[str, FakeLight]]:
    lights = {name: FakeLight() for name in ("green", "yellow", "red")}
    return StatusLed("traffic", lights), lights


@pytest.mark.parametrize("kind", sorted(PATTERNS))
def test_every_condition_has_a_distinct_pattern(kind: str) -> None:
    patterns = [pattern_for(kind, condition) for condition in CONDITIONS]

    assert len(set(patterns)) == len(CONDITIONS)


@pytest.mark.parametrize("kind", sorted(PATTERNS))
def test_fault_blinks_and_levels_do_not_blink_like_fault(kind: str) -> None:
    fault = pattern_for(kind, "fault")

    assert fault.blink == (0.5, 0.5)
    for condition in ("good", "fair", "poor"):
        assert pattern_for(kind, condition) != fault


def test_unknown_condition_counts_as_fault() -> None:
    assert pattern_for("rgb", "sunny") == pattern_for("rgb", "fault")


@pytest.mark.parametrize(
    ("condition", "lit"),
    [("good", "green"), ("fair", "yellow"), ("poor", "red")],
)
def test_traffic_lights_one_led_per_level(condition: str, lit: str) -> None:
    led, lights = traffic()

    led.show(condition)

    assert {name: light.state for name, light in lights.items()} == {
        name: "on" if name == lit else "off" for name in lights
    }


def test_traffic_fault_blinks_yellow_only() -> None:
    led, lights = traffic()
    led.show("good")

    led.show("fault")

    assert lights["yellow"].state == "blink"
    assert lights["yellow"].blink_args == (0.5, 0.5)
    assert lights["green"].state == lights["red"].state == "off"


def test_same_condition_does_not_restart_the_led() -> None:
    led, lights = traffic()
    led.show("fault")
    calls = lights["yellow"].calls

    led.show("fault")

    assert lights["yellow"].calls == calls


def test_change_of_condition_updates_the_led() -> None:
    led, lights = traffic()
    led.show("good")

    led.show("poor")

    assert lights["green"].state == "off"
    assert lights["red"].state == "on"


def test_single_led_blinks_faster_when_poor() -> None:
    light = FakeLight()
    led = StatusLed("single", {"led": light})

    led.show("good")
    assert light.state == "on"

    led.show("poor")
    assert light.state == "blink"
    assert light.blink_args == (0.15, 0.15)


def test_rgb_sets_colour_and_blinks_white_on_fault() -> None:
    light = FakeLight()
    led = StatusLed("rgb", {"rgb": light})

    led.show("fair")
    assert light.color == (1.0, 0.6, 0.0)

    led.show("fault")
    assert light.state == "blink"
    assert light.blink_kwargs == {"on_color": (1.0, 1.0, 1.0), "background": True}


def test_off_and_close() -> None:
    led, lights = traffic()
    led.show("good")

    led.close()

    assert all(light.state == "off" and light.closed for light in lights.values())
    assert led.current is None


def test_create_traffic_led_from_config() -> None:
    config = {"type": "traffic", "pins": {"green": 16, "yellow": 22, "red": 5}}

    led = create_status_led(config, gpio=fake_gpiozero)

    assert isinstance(led, StatusLed)
    assert {name: light.pins for name, light in led.lights.items()} == {
        "green": (16,),
        "yellow": (22,),
        "red": (5,),
    }


def test_create_rgb_led_from_config() -> None:
    config = {"type": "rgb", "pins": {"red": 16, "green": 22, "blue": 5}, "active_high": False}

    led = create_status_led(config, gpio=fake_gpiozero)

    rgb = led.lights["rgb"]
    assert rgb.pins == (16, 22, 5)
    assert rgb.kwargs == {"active_high": False}


def test_none_type_needs_no_gpio() -> None:
    def no_gpio() -> None:
        raise AssertionError("gpiozero must not be imported")

    led = create_status_led({"type": "none"}, gpio=no_gpio)

    assert isinstance(led, LogOnlyLed)
    led.show("good")
    assert led.current == "good"


@pytest.mark.parametrize(
    "config",
    [
        {"type": "laser"},
        {"type": "single", "pins": {}},
        {"type": "single", "pins": {"led": "D16"}},
        {"type": "traffic", "pins": {"green": 16, "yellow": 22}},
    ],
)
def test_invalid_config_is_rejected(config: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        create_status_led(config, gpio=fake_gpiozero)


def test_repository_config_is_valid() -> None:
    config = load_led_config()

    assert isinstance(create_status_led(config, gpio=fake_gpiozero), StatusLed | LogOnlyLed)


def test_missing_led_table_means_no_led(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[conditions.temperature]\ngood = [15, 25]\nfair = [8, 30]\n")

    assert load_led_config(path) == {"type": "none"}
