from pathlib import Path

import pytest

from nc_sensor.conditions import load_thresholds, rate, validate_thresholds

THRESHOLDS = {
    "temperature": {"unit": "°C", "good": [15.0, 25.0], "fair": [8.0, 30.0]},
    "humidity": {"unit": "%", "good": [30.0, 70.0], "fair": [20.0, 85.0]},
}


def rated(temperature: float | None, humidity: float | None, light: float | None = 500) -> str:
    readings = {"temperature": temperature, "humidity": humidity, "light": light}
    return rate(readings, THRESHOLDS)[0]


@pytest.mark.parametrize(
    ("temperature", "expected"),
    [
        (7.9, "poor"),
        (8.0, "fair"),
        (14.9, "fair"),
        (15.0, "good"),
        (20.0, "good"),
        (25.0, "good"),
        (25.1, "fair"),
        (30.0, "fair"),
        (30.1, "poor"),
        (-5.0, "poor"),
    ],
)
def test_temperature_levels_and_boundaries(temperature: float, expected: str) -> None:
    assert rated(temperature, 50.0) == expected


@pytest.mark.parametrize(
    ("humidity", "expected"),
    [
        (19.9, "poor"),
        (20.0, "fair"),
        (30.0, "good"),
        (70.0, "good"),
        (70.1, "fair"),
        (85.0, "fair"),
        (85.1, "poor"),
    ],
)
def test_humidity_levels_and_boundaries(humidity: float, expected: str) -> None:
    assert rated(20.0, humidity) == expected


def test_all_good_has_comfort_reason() -> None:
    result = rate({"temperature": 17.4, "humidity": 62.0, "light": 540}, THRESHOLDS)

    assert result == ("good", "all values in comfort range")


def test_worst_level_wins() -> None:
    assert rated(20.0, 90.0) == "poor"
    assert rated(28.0, 50.0) == "fair"
    assert rated(28.0, 90.0) == "poor"


def test_reason_names_the_worst_values() -> None:
    assert rate({"temperature": 31.5, "humidity": 15.0}, THRESHOLDS) == (
        "poor",
        "temperature high (31.5 °C), humidity low (15 %)",
    )


def test_reason_skips_values_better_than_the_worst() -> None:
    assert rate({"temperature": 28.0, "humidity": 90.0}, THRESHOLDS)[1] == "humidity high (90 %)"


def test_missing_value_is_ignored_and_mentioned() -> None:
    assert rate({"temperature": 20.0, "humidity": None}, THRESHOLDS) == (
        "good",
        "all values in comfort range (humidity missing)",
    )


def test_absent_key_counts_as_missing() -> None:
    assert rate({"temperature": 10.0}, THRESHOLDS)[0] == "fair"


def test_all_values_missing_is_fault() -> None:
    readings = {"temperature": None, "humidity": None, "light": 300}

    assert rate(readings, THRESHOLDS) == ("fault", "no sensor values")


def test_light_does_not_change_the_rating() -> None:
    assert rated(20.0, 50.0, light=0) == "good"
    assert rated(20.0, 50.0, light=None) == "good"
    assert rated(None, None, light=900) == "fault"


def test_unit_is_optional() -> None:
    thresholds = {"temperature": {"good": [15, 25], "fair": [8, 30]}}

    assert rate({"temperature": 5}, thresholds) == ("poor", "temperature low (5)")


def test_repository_config_matches_architecture_doc() -> None:
    assert load_thresholds() == THRESHOLDS


def test_load_thresholds_from_file(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text("[conditions.temperature]\ngood = [18, 22]\nfair = [10, 28]\n")

    thresholds = load_thresholds(config)

    assert thresholds == {"temperature": {"good": [18, 22], "fair": [10, 28]}}
    assert rate({"temperature": 25.0}, thresholds)[0] == "fair"


@pytest.mark.parametrize(
    "tables",
    [
        None,
        {},
        {"temperature": [15, 25]},
        {"temperature": {"good": [15, 25]}},
        {"temperature": {"good": [15], "fair": [8, 30]}},
        {"temperature": {"good": [25, 15], "fair": [8, 30]}},
        {"temperature": {"good": [5, 25], "fair": [8, 30]}},
        {"temperature": {"good": [15, "x"], "fair": [8, 30]}},
        {"temperature": {"good": [True, 25], "fair": [8, 30]}},
    ],
)
def test_invalid_config_is_rejected(tables: object) -> None:
    with pytest.raises(ValueError):
        validate_thresholds(tables)
