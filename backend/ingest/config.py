"""Settings of the mqtt-ingest service, from environment variables and the repo `.env` file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class IngestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    # The ingest has its own broker user; MQTT_USERNAME in .env belongs to the sensor node.
    ingest_mqtt_username: str = "ingest"
    ingest_mqtt_password: str = ""

    influxdb_url: str = "http://localhost:8086"
    influxdb_token: str = ""
    influxdb_org: str = "naturecheckpoint"
    influxdb_bucket: str = "environment"
