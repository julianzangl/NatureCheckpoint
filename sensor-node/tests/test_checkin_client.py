import json
import urllib.error
from typing import Any

import pytest

from nc_sensor import checkin
from nc_sensor.checkin import CheckinClient, lcd_lines
from nc_sensor.sensors.nfc import card_hash

UID = b"\xde\xad\xbe\xef"
STAMPED = {
    "status": "stamped",
    "station": "Duck pond",
    "stamps_this_month": 2,
    "goal": 6,
    "reward": None,
}


class FakeReply:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> "FakeReply":
        return self

    def __exit__(self, *args: object) -> None:
        pass


def fake_urlopen(monkeypatch: pytest.MonkeyPatch, result: Any) -> list[Any]:
    """Replace urlopen; returns the list of captured requests."""
    requests: list[Any] = []

    def urlopen(request: Any, timeout: float) -> FakeReply:
        requests.append(request)
        if isinstance(result, Exception):
            raise result
        return FakeReply(json.dumps(result).encode())

    monkeypatch.setattr(checkin.urllib.request, "urlopen", urlopen)
    return requests


def client() -> CheckinClient:
    return CheckinClient("http://backend:8000", "device-secret", "salt")


# --- LCD lines ----------------------------------------------------------------------------------


def test_lcd_lines_stamped() -> None:
    assert lcd_lines(STAMPED) == ("Stamp! 2/6", "Duck pond")


def test_lcd_lines_already_stamped() -> None:
    response = {**STAMPED, "status": "already_stamped"}

    assert lcd_lines(response) == ("Already 2/6", "Come back tmrw")


def test_lcd_lines_reward_shows_the_code() -> None:
    response = {**STAMPED, "stamps_this_month": 6, "reward": {"code": "NC-7K2QX9AB"}}

    assert lcd_lines(response) == ("Voucher! 6/6", "NC-7K2QX9AB")


def test_lcd_lines_are_cut_to_16_chars() -> None:
    response = {**STAMPED, "station": "A very long station name", "stamps_this_month": 100}

    assert all(len(line) <= 16 for line in lcd_lines(response))


# --- HTTP ---------------------------------------------------------------------------------------


def test_check_in_success(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = fake_urlopen(monkeypatch, STAMPED)

    outcome = client().check_in("station-1", UID)

    assert outcome.ok is True
    assert outcome.response == STAMPED
    assert outcome.lines == ("Stamp! 2/6", "Duck pond")
    (request,) = requests
    assert request.full_url == "http://backend:8000/api/checkins/card"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer device-secret"


def test_check_in_sends_only_the_card_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = fake_urlopen(monkeypatch, STAMPED)

    client().check_in("station-2", UID)

    raw = requests[0].data.decode()
    assert json.loads(raw) == {"station_id": "station-2", "card_hash": card_hash(UID, "salt")}
    assert UID.hex() not in raw


@pytest.mark.parametrize(("code", "message"), [(401, "Device error"), (429, "Slow down")])
def test_http_error_is_shown(monkeypatch: pytest.MonkeyPatch, code: int, message: str) -> None:
    error = urllib.error.HTTPError("http://backend", code, "error", None, None)  # type: ignore[arg-type]
    fake_urlopen(monkeypatch, error)

    outcome = client().check_in("station-1", UID)

    assert outcome.ok is False
    assert outcome.lines == ("Check-in failed", message)
    assert outcome.response is None


def test_unreachable_server_is_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_urlopen(monkeypatch, urllib.error.URLError("connection refused"))

    outcome = client().check_in("station-1", UID)

    assert outcome.ok is False
    assert outcome.lines == ("Check-in failed", "Server offline")
