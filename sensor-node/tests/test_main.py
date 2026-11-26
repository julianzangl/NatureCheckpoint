from typing import Any

import pytest

from nc_sensor.main import Screen, sample_once
from nc_sensor.settings import Settings

THRESHOLDS = {
    "temperature": {"good": [15.0, 25.0], "fair": [8.0, 30.0]},
    "humidity": {"good": [30.0, 70.0], "fair": [20.0, 85.0]},
}


class FakeDisplay:
    def __init__(self) -> None:
        self.shown: list[tuple[str, str]] = []

    def show(self, line1: str, line2: str) -> None:
        self.shown.append((line1, line2))

    def close(self) -> None:
        pass


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr("nc_sensor.main.time.monotonic", fake)
    return fake


def test_status_is_shown_right_away(clock: FakeClock) -> None:
    display = FakeDisplay()

    Screen(display).status(("Walk: GOOD", "21C 55%"))

    assert display.shown == [("Walk: GOOD", "21C 55%")]


def test_flash_holds_the_display(clock: FakeClock) -> None:
    display = FakeDisplay()
    screen = Screen(display)

    screen.flash(("Stamp! 1/6", "Duck pond"), seconds=5)
    clock.now += 4.9
    screen.status(("Walk: GOOD", "21C 55%"))
    screen.refresh()

    assert display.shown == [("Stamp! 1/6", "Duck pond")]


def test_status_returns_after_the_hold(clock: FakeClock) -> None:
    display = FakeDisplay()
    screen = Screen(display)

    screen.flash(("Stamp! 1/6", "Duck pond"), seconds=5)
    screen.status(("Walk: FAIR", "9C 55%"))
    clock.now += 5
    screen.refresh()

    assert display.shown[-1] == ("Walk: FAIR", "9C 55%")


class FakeSensor:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values

    def read(self) -> dict[str, Any]:
        return self.values


def test_sample_once_builds_one_payload_per_station() -> None:
    settings = Settings(station_ids=["station-1", "station-2"])
    dht = FakeSensor({"temperature": 20.0, "humidity": 50.0})
    light = FakeSensor({"light": 400.0})

    values, payloads = sample_once(settings, dht, light, THRESHOLDS)  # type: ignore[arg-type]

    assert values == {"temperature": 20.0, "humidity": 50.0, "light": 400.0}
    assert [p["station_id"] for p in payloads] == ["station-1", "station-2"]
    assert {p["condition"] for p in payloads} == {"good"}
    # Both checkpoints share one sample, so they carry the same timestamp.
    assert payloads[0]["timestamp"] == payloads[1]["timestamp"]
