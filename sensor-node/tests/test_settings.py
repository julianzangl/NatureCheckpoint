from pathlib import Path

import pytest

from nc_sensor.settings import NfcReaderConfig, load_settings, parse_readers, parse_station_ids

ENV_KEYS = [
    "STATION_ID",
    "STATION_IDS",
    "SAMPLE_INTERVAL_S",
    "MQTT_HOST",
    "MQTT_PORT",
    "MQTT_USERNAME",
    "MQTT_PASSWORD",
    "BACKEND_URL",
    "DEVICE_TOKEN",
    "CARD_SALT",
]

CONFIG = """
[lcd]
enabled = true

[nfc]
readers = [
  { bus = 1, station_id = "station-1" },
  { bus = 3, station_id = "station-2" },
]
"""


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # load_dotenv never overrides existing variables, and it writes to os.environ directly.
    # Setting then deleting each key makes monkeypatch remove what load_dotenv adds later.
    for key in ENV_KEYS:
        monkeypatch.setenv(key, "placeholder")
        monkeypatch.delenv(key)


@pytest.mark.parametrize(
    ("primary", "extra", "expected"),
    [
        ("station-1", "", ["station-1"]),
        ("station-1", "station-2", ["station-1", "station-2"]),
        ("station-2", "station-1,station-2", ["station-2", "station-1"]),
        (" station-1 ", " station-2 , ,station-3,", ["station-1", "station-2", "station-3"]),
        ("", "station-2", ["station-2"]),
    ],
)
def test_parse_station_ids(primary: str, extra: str, expected: list[str]) -> None:
    assert parse_station_ids(primary, extra) == expected


def test_parse_readers() -> None:
    config = {"nfc": {"readers": [{"bus": "3", "station_id": "station-2"}]}}

    assert parse_readers(config) == [NfcReaderConfig(bus=3, station_id="station-2")]


def test_parse_readers_without_nfc_table_is_empty() -> None:
    assert parse_readers({}) == []


def test_load_settings_from_env_file_and_config(tmp_path: Path, clean_env: None) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "STATION_ID=station-1\n"
        "STATION_IDS=station-2\n"
        "MQTT_PORT=1884\n"
        "BACKEND_URL=http://pi.local:8000/\n"
        "DEVICE_TOKEN=token\n"
        "CARD_SALT=salt\n",
        encoding="utf-8",
    )
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")

    settings = load_settings(env_file, config)

    assert settings.station_ids == ["station-1", "station-2"]
    assert settings.mqtt_port == 1884
    assert settings.backend_url == "http://pi.local:8000"
    assert settings.device_token == "token"
    assert settings.card_salt == "salt"
    assert settings.lcd is True
    assert settings.readers == [
        NfcReaderConfig(bus=1, station_id="station-1"),
        NfcReaderConfig(bus=3, station_id="station-2"),
    ]


def test_load_settings_defaults(tmp_path: Path, clean_env: None) -> None:
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")

    settings = load_settings(tmp_path / "missing.env", config)

    assert settings.station_ids == ["station-1"]
    assert settings.mqtt_host == "localhost"
    assert settings.mqtt_port == 1883
    assert settings.backend_url == "http://localhost:8000"
    assert settings.readers == []
    assert settings.lcd is False
