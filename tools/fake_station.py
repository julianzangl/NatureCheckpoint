"""Publish plausible fake readings for station-1 and station-2, so the server side can be built
and demoed without a Raspberry Pi.

Payloads follow docs/architecture.md (section 4). Broker settings come from the repository's
.env (MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD) and can be overridden by options.

Examples (from the repository root, with the dev venv active):
    python tools/fake_station.py                   # every 10 s until Ctrl+C
    python tools/fake_station.py --count 1         # one round, then exit
    python tools/fake_station.py --interval 2 --invalid
"""

import argparse
import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from paho.mqtt.enums import CallbackAPIVersion

REPO_ROOT = Path(__file__).resolve().parents[1]
QOS = 1


@dataclass
class FakeStation:
    """Values follow a slow random walk, so the dashboard shows curves instead of noise."""

    station_id: str
    temperature: float
    humidity: float
    light: float
    started: float = field(default_factory=time.monotonic)

    def step(self, rng: random.Random) -> None:
        self.temperature = clamp(self.temperature + rng.uniform(-0.4, 0.4), 2, 34)
        self.humidity = clamp(self.humidity + rng.uniform(-1.5, 1.5), 15, 95)
        self.light = clamp(self.light + rng.uniform(-60, 60), 0, 1000)

    def readings(self, now: datetime, rng: random.Random) -> dict[str, object]:
        # Now and then a sensor fails, like the real DHT does.
        temperature = None if rng.random() < 0.03 else round(self.temperature, 1)
        humidity = None if rng.random() < 0.03 else round(self.humidity, 1)
        condition, reason = rate(temperature, humidity)
        return {
            "station_id": self.station_id,
            "timestamp": iso(now),
            "temperature": temperature,
            "humidity": humidity,
            "light": round(self.light),
            "condition": condition,
            "condition_reason": reason,
        }

    def health(self, now: datetime, rng: random.Random) -> dict[str, object]:
        return {
            "station_id": self.station_id,
            "timestamp": iso(now),
            "cpu_temp": round(rng.uniform(45, 62), 1),
            "load1": round(rng.uniform(0.05, 0.8), 2),
            "uptime_s": int(time.monotonic() - self.started) + 3600,
        }


def rate(temperature: float | None, humidity: float | None) -> tuple[str, str]:
    """Rough copy of the thresholds in docs/architecture.md. The real rating lives on the Pi."""
    levels = []
    if temperature is not None:
        levels.append(level(temperature, good=(15, 25), fair=(8, 30)))
    if humidity is not None:
        levels.append(level(humidity, good=(30, 70), fair=(20, 85)))
    if not levels:
        return "fault", "no sensor values"
    worst = max(levels, key=["good", "fair", "poor"].index)
    return worst, "fake station"


def level(value: float, good: tuple[float, float], fair: tuple[float, float]) -> str:
    if good[0] <= value <= good[1]:
        return "good"
    if fair[0] <= value <= fair[1]:
        return "fair"
    return "poor"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def iso(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_args() -> argparse.Namespace:
    load_dotenv(REPO_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--username", default=os.getenv("MQTT_USERNAME") or "station-1")
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD", ""))
    parser.add_argument("--stations", nargs="+", default=["station-1", "station-2"])
    parser.add_argument("--interval", type=float, default=10, help="seconds between rounds")
    parser.add_argument("--count", type=int, default=0, help="number of rounds, 0 = endless")
    parser.add_argument("--seed", type=int, help="random seed for repeatable values")
    parser.add_argument(
        "--invalid",
        action="store_true",
        help="also send one malformed message per round, to test that the ingest skips it",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    stations = [
        FakeStation(sid, rng.uniform(14, 22), rng.uniform(45, 70), rng.uniform(200, 700))
        for sid in args.stations
    ]

    client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    client.username_pw_set(args.username, args.password)
    client.connect(args.host, args.port)
    client.loop_start()

    try:
        rounds = 0
        while args.count == 0 or rounds < args.count:
            now = datetime.now(UTC)
            for station in stations:
                station.step(rng)
                publish(
                    client,
                    f"naturecheckpoint/{station.station_id}/readings",
                    station.readings(now, rng),
                )
                publish(
                    client,
                    f"naturecheckpoint/{station.station_id}/health",
                    station.health(now, rng),
                )
            if args.invalid:
                info = client.publish(
                    f"naturecheckpoint/{stations[0].station_id}/readings", "{oops", QOS
                )
                info.wait_for_publish(timeout=5)
                print("sent one invalid message")
            rounds += 1
            if args.count == 0 or rounds < args.count:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


def publish(client: mqtt.Client, topic: str, payload: dict[str, object]) -> None:
    info = client.publish(topic, json.dumps(payload), qos=QOS)
    info.wait_for_publish(timeout=5)
    if not info.is_published():
        raise SystemExit(f"could not publish to {topic}; check broker address and login")
    print(topic, json.dumps(payload))


if __name__ == "__main__":
    main()
