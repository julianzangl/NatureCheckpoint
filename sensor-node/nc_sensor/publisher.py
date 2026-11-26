"""MQTT publisher of the sensor node (#12): QoS 1, not retained, reconnects on its own."""

from __future__ import annotations

import json
import logging
from typing import Any

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

QOS = 1


class MqttPublisher:
    def __init__(
        self,
        host: str,
        port: int,
        client_id: str,
        username: str = "",
        password: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if username:
            self.client.username_pw_set(username, password or None)
        # Keep QoS 1 messages while the broker is away; paho sends them after reconnecting.
        self.client.max_queued_messages_set(1000)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client: Any, userdata: Any, flags: Any, reason: Any, props: Any) -> None:
        if reason.is_failure:
            logger.error("MQTT connect to %s:%d refused: %s", self.host, self.port, reason)
        else:
            logger.info("MQTT connected to %s:%d", self.host, self.port)

    def _on_disconnect(
        self, client: Any, userdata: Any, flags: Any, reason: Any, props: Any
    ) -> None:
        logger.warning("MQTT disconnected: %s", reason)

    def start(self) -> None:
        # connect_async + loop_start: the first connect may fail, paho keeps retrying.
        self.client.connect_async(self.host, self.port, keepalive=60)
        self.client.loop_start()

    def publish(self, topic: str, payload: dict[str, Any]) -> bool:
        info = self.client.publish(topic, json.dumps(payload), qos=QOS, retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.warning("MQTT publish to %s not queued: %s", topic, mqtt.error_string(info.rc))
            return False
        return True

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
