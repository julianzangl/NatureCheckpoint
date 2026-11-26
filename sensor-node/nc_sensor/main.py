"""Sensor node of a checkpoint (#6): sample, rate, show, publish, and handle card taps.

Every `SAMPLE_INTERVAL_S` the node reads all sensors, rates the walk conditions, updates the
status LED and the LCD, publishes the reading via MQTT and appends it to a local log. A
second thread polls the NFC readers and sends a card check-in to the backend for each tap.

Run on the Pi: ``python -m nc_sensor.main`` (systemd: deploy/pi/nc-sensor-node.service).
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import threading
import time
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from typing import Any

from nc_sensor.actuators.lcd import Display, create_display, status_lines
from nc_sensor.actuators.led import LogOnlyLed, create_status_led, load_led_config
from nc_sensor.checkin import CheckinClient
from nc_sensor.conditions import load_thresholds
from nc_sensor.payload import build_reading, readings_topic
from nc_sensor.publisher import MqttPublisher
from nc_sensor.sensors.light import LightSensor
from nc_sensor.sensors.nfc import CardReader, is_random_uid
from nc_sensor.sensors.temp_humidity import TempHumiditySensor
from nc_sensor.settings import Settings, load_settings

logger = logging.getLogger("nc_sensor")

# How long the LCD shows a check-in result before it returns to the conditions.
CHECKIN_DISPLAY_S = 5.0
NFC_POLL_S = 0.1


def reading_log(settings: Settings) -> logging.Logger:
    """Local JSON-lines log of every sample, so data survives a broker outage."""
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("nc_sensor.readings")
    log.propagate = False
    handler = RotatingFileHandler(
        settings.log_dir / "readings.jsonl", maxBytes=5_000_000, backupCount=3
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    return log


class Screen:
    """Shares the LCD between the sampling loop and check-in feedback."""

    def __init__(self, display: Display) -> None:
        self.display = display
        self._status = ("NatureCheckpoint", "starting...")
        self._hold_until = 0.0
        self._lock = threading.Lock()

    def status(self, lines: tuple[str, str]) -> None:
        with self._lock:
            self._status = lines
            if time.monotonic() >= self._hold_until:
                self.display.show(*lines)

    def flash(self, lines: tuple[str, str], seconds: float = CHECKIN_DISPLAY_S) -> None:
        with self._lock:
            self._hold_until = time.monotonic() + seconds
            self.display.show(*lines)

    def refresh(self) -> None:
        with self._lock:
            if time.monotonic() >= self._hold_until:
                self.display.show(*self._status)


def nfc_loop(settings: Settings, screen: Screen, stop: threading.Event) -> None:
    readers = [(CardReader(r.bus), r.station_id) for r in settings.readers]
    client = CheckinClient(settings.backend_url, settings.device_token, settings.card_salt)
    logger.info("NFC: %d reader(s): %s", len(readers), [(r.bus_number, s) for r, s in readers])
    while not stop.is_set():
        for reader, station_id in readers:
            uid = reader.poll(time.monotonic())
            if uid is None:
                continue
            if is_random_uid(uid):
                logger.info("NFC at %s: random UID (phone or bank card), no check-in", station_id)
                screen.flash(("Phone/random ID", "Use a card"))
                continue
            screen.flash(("Checking in...", station_id))
            outcome = client.check_in(station_id, uid)
            screen.flash(outcome.lines)
        screen.refresh()
        stop.wait(NFC_POLL_S)


def sample_once(
    settings: Settings,
    dht: TempHumiditySensor,
    light: LightSensor,
    thresholds: Any,
) -> tuple[dict[str, float | None], list[dict[str, Any]]]:
    values: dict[str, float | None] = {**dht.read(), **light.read()}
    now = datetime.now(UTC)
    payloads = [build_reading(sid, now, values, thresholds) for sid in settings.station_ids]
    return values, payloads


def run(settings: Settings, once: bool = False) -> None:
    thresholds = load_thresholds()
    dht = TempHumiditySensor()
    light = LightSensor()
    try:
        led = create_status_led(load_led_config())
    except Exception as exc:  # e.g. GPIO busy: run without LED rather than not at all
        logger.error("status LED not available (%s), logging instead", exc)
        led = LogOnlyLed()
    screen = Screen(create_display(settings.lcd))
    publisher = MqttPublisher(
        settings.mqtt_host,
        settings.mqtt_port,
        client_id=f"sensor-node-{settings.station_ids[0]}",
        username=settings.mqtt_username,
        password=settings.mqtt_password,
    )
    log = reading_log(settings)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    publisher.start()
    nfc = None
    if settings.readers and not once:
        if not settings.device_token or not settings.card_salt:
            logger.error("DEVICE_TOKEN and CARD_SALT must be set for card check-ins")
        else:
            nfc = threading.Thread(target=nfc_loop, args=(settings, screen, stop), daemon=True)
            nfc.start()
    logger.info("sampling every %.0f s for %s", settings.sample_interval_s, settings.station_ids)
    try:
        while not stop.is_set():
            started = time.monotonic()
            values, payloads = sample_once(settings, dht, light, thresholds)
            condition = payloads[0]["condition"]
            led.show(condition)
            screen.status(status_lines(values, condition))
            for payload in payloads:
                publisher.publish(readings_topic(payload["station_id"]), payload)
                log.info(json.dumps(payload))
            logger.info(
                "%s: %s (%s)",
                ", ".join(settings.station_ids),
                condition,
                payloads[0]["condition_reason"],
            )
            if once:
                time.sleep(1)  # let paho deliver the QoS 1 message
                break
            stop.wait(max(0.0, settings.sample_interval_s - (time.monotonic() - started)))
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if nfc is not None:
            nfc.join(timeout=2)
        publisher.stop()
        led.close()
        screen.display.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="NatureCheckpoint sensor node")
    parser.add_argument("--once", action="store_true", help="take one sample and exit")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run(load_settings(), once=args.once)


if __name__ == "__main__":
    main()
