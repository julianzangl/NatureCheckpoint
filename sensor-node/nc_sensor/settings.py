"""Sensor-node settings: secrets and hosts from `.env` (D17), hardware from config.toml."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.toml"


@dataclass(frozen=True)
class NfcReaderConfig:
    bus: int
    station_id: str


@dataclass(frozen=True)
class Settings:
    station_ids: list[str]
    sample_interval_s: float = 10.0
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    backend_url: str = "http://localhost:8000"
    device_token: str = ""
    card_salt: str = ""
    readers: list[NfcReaderConfig] = field(default_factory=list)
    lcd: bool = False
    log_dir: Path = REPO_ROOT / "data"


def parse_station_ids(primary: str, extra: str) -> list[str]:
    """`STATION_ID` first, then `STATION_IDS` (comma separated), without duplicates."""
    ids = [primary.strip()] + [part.strip() for part in extra.split(",")]
    return list(dict.fromkeys(i for i in ids if i))


def parse_readers(config: dict[str, Any]) -> list[NfcReaderConfig]:
    readers = config.get("nfc", {}).get("readers", [])
    return [NfcReaderConfig(bus=int(r["bus"]), station_id=str(r["station_id"])) for r in readers]


def load_settings(env_file: Path = REPO_ROOT / ".env", config_path: Path = CONFIG_PATH) -> Settings:
    load_dotenv(env_file)
    with config_path.open("rb") as file:
        config = tomllib.load(file)
    env = os.environ
    return Settings(
        station_ids=parse_station_ids(
            env.get("STATION_ID", "station-1"), env.get("STATION_IDS", "")
        ),
        sample_interval_s=float(env.get("SAMPLE_INTERVAL_S", "10")),
        mqtt_host=env.get("MQTT_HOST", "localhost"),
        mqtt_port=int(env.get("MQTT_PORT", "1883")),
        mqtt_username=env.get("MQTT_USERNAME", ""),
        mqtt_password=env.get("MQTT_PASSWORD", ""),
        backend_url=env.get("BACKEND_URL", "http://localhost:8000").rstrip("/"),
        device_token=env.get("DEVICE_TOKEN", ""),
        card_salt=env.get("CARD_SALT", ""),
        readers=parse_readers(config),
        lcd=bool(config.get("lcd", {}).get("enabled", False)),
    )
