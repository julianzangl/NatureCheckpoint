"""Card check-in from the Pi (#9, #16): a tapped card becomes `POST /api/checkins/card`."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from nc_sensor.sensors.nfc import card_hash

logger = logging.getLogger(__name__)

TIMEOUT_S = 5


@dataclass(frozen=True)
class CheckinOutcome:
    ok: bool
    lines: tuple[str, str]  # what the LCD shows
    response: dict[str, Any] | None = None


def lcd_lines(response: dict[str, Any]) -> tuple[str, str]:
    """Two 16-character LCD lines for a check-in response."""
    stamps = f"{response['stamps_this_month']}/{response['goal']}"
    reward = response.get("reward")
    if reward:
        return ("Voucher! " + stamps)[:16], reward["code"][:16]
    if response["status"] == "stamped":
        return f"Stamp! {stamps}"[:16], str(response["station"])[:16]
    return f"Already {stamps}"[:16], "Come back tmrw"[:16]


class CheckinClient:
    def __init__(self, backend_url: str, device_token: str, salt: str) -> None:
        self.url = f"{backend_url}/api/checkins/card"
        self.device_token = device_token
        self.salt = salt

    def check_in(self, station_id: str, uid: bytes) -> CheckinOutcome:
        body = json.dumps({"station_id": station_id, "card_hash": card_hash(uid, self.salt)})
        request = urllib.request.Request(
            self.url,
            data=body.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.device_token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as reply:
                data = json.loads(reply.read())
        except urllib.error.HTTPError as exc:
            logger.warning("check-in at %s rejected: HTTP %d", station_id, exc.code)
            message = {429: "Slow down", 401: "Device error", 404: "Unknown station"}
            return CheckinOutcome(
                False, ("Check-in failed", message.get(exc.code, f"HTTP {exc.code}"))
            )
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.warning("check-in at %s failed: %s", station_id, exc)
            return CheckinOutcome(False, ("Check-in failed", "Server offline"))
        logger.info(
            "check-in at %s: %s, %s/%s stamps",
            station_id,
            data["status"],
            data["stamps_this_month"],
            data["goal"],
        )
        return CheckinOutcome(True, lcd_lines(data), data)
