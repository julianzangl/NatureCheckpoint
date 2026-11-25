import math
from pathlib import Path

import pytest

from nc_sensor.sensors.light import (
    CONFIG_PATH,
    DARK,
    SHADE,
    SUN,
    LightSensor,
    classify,
    load_light_thresholds,
    validate,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0.0),
        (540, 540.0),
        (1000.0, 1000.0),
        (-1, None),
        (1000.1, None),
        (None, None),
        (math.nan, None),
        ("bright", None),
    ],
)
def test_validate(value, expected):
    assert validate(value, 0.0, 1000.0) == expected


@pytest.mark.parametrize(
    ("light", "expected"),
    [(0.0, DARK), (99.9, DARK), (100.0, SHADE), (600.0, SHADE), (600.1, SUN), (None, None)],
)
def test_classify(light, expected):
    assert classify(light, dark_below=100.0, sun_above=600.0) == expected


def test_repository_config_has_valid_light_thresholds():
    dark_below, sun_above = load_light_thresholds(CONFIG_PATH)
    assert 0 <= dark_below < sun_above <= 1000


@pytest.mark.parametrize(
    "content",
    [
        "[conditions]\n",
        "[light]\ndark_below = 100\n",
        '[light]\ndark_below = "low"\nsun_above = 600\n',
        "[light]\ndark_below = 700\nsun_above = 600\n",
        "[light]\ndark_below = 100\nsun_above = 1200\n",
    ],
)
def test_load_light_thresholds_rejects_broken_config(tmp_path: Path, content):
    path = tmp_path / "config.toml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_light_thresholds(path)


class FakeAdc:
    """Returns the queued results in order; an Exception instance is raised instead."""

    def __init__(self, results):
        self.results = list(results)
        self.channels = []

    def read(self, channel):
        self.channels.append(channel)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def make_sensor(adc, sleeps=None, **kwargs):
    return LightSensor(
        adc_factory=lambda: adc,
        sleep=(sleeps.append if sleeps is not None else lambda s: None),
        **kwargs,
    )


def test_read_returns_light_from_default_channel_a2():
    adc = FakeAdc([540])
    assert make_sensor(adc).read() == {"light": 540.0}
    assert adc.channels == [2]


def test_read_uses_given_channel():
    adc = FakeAdc([12])
    assert make_sensor(adc, channel=0).read() == {"light": 12.0}
    assert adc.channels == [0]


def test_read_retries_after_error_then_succeeds():
    sleeps = []
    adc = FakeAdc([OSError("I2C error"), 300])
    assert make_sensor(adc, sleeps).read() == {"light": 300.0}
    assert len(adc.channels) == 2
    assert sleeps == [0.2]


def test_read_returns_none_after_three_failures():
    sleeps = []
    adc = FakeAdc([OSError("I2C error"), 5000, None])
    assert make_sensor(adc, sleeps).read() == {"light": None}
    assert len(adc.channels) == 3
    assert len(sleeps) == 2


def test_read_does_not_raise_when_adc_cannot_be_created():
    def broken_factory():
        raise ImportError("grove.py not installed")

    sensor = LightSensor(adc_factory=broken_factory, sleep=lambda s: None)
    assert sensor.read() == {"light": None}
