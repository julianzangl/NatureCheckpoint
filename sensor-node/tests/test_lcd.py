import pytest

from nc_sensor.actuators import lcd
from nc_sensor.actuators.lcd import WIDTH, LogOnlyDisplay, create_display, pad, status_lines


def test_status_lines_show_rating_values_and_hint() -> None:
    assert status_lines({"temperature": 21.4, "humidity": 55.0}, "good") == (
        "Walk: GOOD",
        "21C 55% Tap card",
    )


def test_fault_shows_sensor_fault() -> None:
    first, second = status_lines({"temperature": None, "humidity": None}, "fault")

    assert first == "Sensor fault"
    assert second == "-- -- Tap card"


def test_missing_value_is_shown_as_dashes() -> None:
    assert status_lines({"temperature": 9.0}, "fair") == ("Walk: FAIR", "9C -- Tap card")


def test_hint_is_dropped_when_it_does_not_fit() -> None:
    # "-10C 100%" plus " Tap card" would be 18 characters.
    assert status_lines({"temperature": -10.0, "humidity": 100.0}, "poor")[1] == "-10C 100%"


@pytest.mark.parametrize(
    "values",
    [
        {"temperature": 21.0, "humidity": 55.0},
        {"temperature": -19.6, "humidity": 99.9},
        {"temperature": None, "humidity": 100.0},
        {},
    ],
)
@pytest.mark.parametrize("condition", ["good", "fair", "poor", "fault"])
def test_lines_fit_the_display(values: dict, condition: str) -> None:
    assert all(len(line) <= WIDTH for line in status_lines(values, condition))


def test_pad_fills_and_cuts_to_width() -> None:
    assert pad("Hi") == "Hi" + " " * 14
    assert pad("x" * 20) == "x" * 16


def test_disabled_display_only_logs() -> None:
    assert isinstance(create_display(False), LogOnlyDisplay)


def test_missing_lcd_falls_back_to_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_lcd() -> None:
        raise OSError("no device at 0x3e")

    monkeypatch.setattr(lcd, "GroveLcd", no_lcd)

    assert isinstance(create_display(True), LogOnlyDisplay)
