import math

import pytest

from nc_sensor.sensors.temp_humidity import (
    HUMIDITY_RANGE_PCT,
    TEMPERATURE_RANGE_C,
    TempHumiditySensor,
    validate,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (21.5, 21.5),
        (-20.0, -20.0),
        (50.0, 50.0),
        (0, 0.0),
        (-20.1, None),
        (50.1, None),
        (None, None),
        (math.nan, None),
        ("abc", None),
        (True, None),
    ],
)
def test_validate_temperature(value, expected):
    assert validate(value, *TEMPERATURE_RANGE_C) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, 0.0), (100.0, 100.0), (62, 62.0), (-0.1, None), (100.1, None)],
)
def test_validate_humidity(value, expected):
    assert validate(value, *HUMIDITY_RANGE_PCT) == expected


class FakeDriver:
    """Returns the queued results in order; an Exception instance is raised instead."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def read(self):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def make_sensor(driver, sleeps=None):
    return TempHumiditySensor(
        driver_factory=lambda dht_type, pin: driver,
        sleep=(sleeps.append if sleeps is not None else lambda s: None),
    )


def test_read_returns_values_with_units_as_keys():
    driver = FakeDriver([(62.0, 17.4)])
    assert make_sensor(driver).read() == {"temperature": 17.4, "humidity": 62.0}
    assert driver.calls == 1


def test_read_retries_after_error_then_succeeds():
    sleeps = []
    driver = FakeDriver([OSError("timeout"), (55.0, 20.0)])
    assert make_sensor(driver, sleeps).read() == {"temperature": 20.0, "humidity": 55.0}
    assert driver.calls == 2
    assert sleeps == [2.0]


def test_read_returns_none_after_three_failures():
    sleeps = []
    driver = FakeDriver([RuntimeError("checksum"), (None, None), (500.0, 999.0)])
    assert make_sensor(driver, sleeps).read() == {"temperature": None, "humidity": None}
    assert driver.calls == 3
    assert len(sleeps) == 2


def test_read_keeps_valid_value_when_other_is_implausible():
    driver = FakeDriver([(140.0, 18.0)])
    assert make_sensor(driver).read() == {"temperature": 18.0, "humidity": None}


def test_read_does_not_raise_when_driver_cannot_be_created():
    def broken_factory(dht_type, pin):
        raise ImportError("grove.py not installed")

    sensor = TempHumiditySensor(driver_factory=broken_factory, sleep=lambda s: None)
    assert sensor.read() == {"temperature": None, "humidity": None}


def test_default_port_is_grove_d18():
    sensor = TempHumiditySensor()
    assert sensor.pin == 18
    assert sensor.dht_type == "11"
