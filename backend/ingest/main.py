"""mqtt-ingest: subscribe to the checkpoint topics and write every valid message to InfluxDB.

Run with `python -m ingest.main` (from `backend/`, or in the backend Docker image).
Invalid messages are logged and skipped. The service never stops because of a bad message,
and it reconnects on its own when the broker goes away.
"""

import logging
import signal
from types import FrameType

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS, WriteApi
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.reasoncodes import ReasonCode

from ingest.config import IngestSettings
from ingest.points import InvalidMessage, payload_to_point

log = logging.getLogger("mqtt-ingest")

TOPICS = ["naturecheckpoint/+/readings", "naturecheckpoint/+/health"]
QOS = 1
CLIENT_ID = "mqtt-ingest"


class Ingest:
    def __init__(self, settings: IngestSettings, write_api: WriteApi) -> None:
        self.settings = settings
        self.write_api = write_api

    def on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            log.error("broker refused the connection: %s", reason_code)
            return
        log.info("connected to %s:%s", self.settings.mqtt_host, self.settings.mqtt_port)
        # Subscribing here (not once at start) restores the subscriptions after a reconnect.
        client.subscribe([(topic, QOS) for topic in TOPICS])

    def on_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.DisconnectFlags,
        reason_code: ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code != 0:
            log.warning("disconnected from broker (%s), reconnecting", reason_code)

    def on_message(self, client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        try:
            point = payload_to_point(msg.topic, msg.payload)
        except InvalidMessage as exc:
            log.warning("skipped message on %s: %s", msg.topic, exc)
            return

        try:
            self.write_api.write(
                bucket=self.settings.influxdb_bucket, org=self.settings.influxdb_org, record=point
            )
        except Exception:
            # Catch everything: an InfluxDB outage must not kill the subscriber loop.
            log.exception("could not write message on %s to InfluxDB", msg.topic)
            return
        log.debug("stored %s", point.to_line_protocol())


def build_client(settings: IngestSettings, ingest: Ingest) -> mqtt.Client:
    # A fixed client ID with a persistent session lets the broker queue QoS 1 messages
    # while the ingest restarts.
    client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        clean_session=False,
    )
    client.username_pw_set(settings.ingest_mqtt_username, settings.ingest_mqtt_password)
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.on_connect = ingest.on_connect
    client.on_disconnect = ingest.on_disconnect
    client.on_message = ingest.on_message
    return client


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = IngestSettings()
    if not settings.influxdb_token:
        raise SystemExit("INFLUXDB_TOKEN is not set")

    with InfluxDBClient(
        url=settings.influxdb_url, token=settings.influxdb_token, org=settings.influxdb_org
    ) as influx:
        ingest = Ingest(settings, influx.write_api(write_options=SYNCHRONOUS))
        client = build_client(settings, ingest)

        def stop(signum: int, frame: FrameType | None) -> None:
            log.info("stopping")
            client.disconnect()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

        client.connect_async(settings.mqtt_host, settings.mqtt_port)
        # retry_first_connection: the broker may start after the ingest (docker compose up).
        client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
