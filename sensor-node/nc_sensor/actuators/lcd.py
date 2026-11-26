"""Grove 16x2 LCD (JHD1802, I2C 0x3E): walk condition and check-in feedback on site."""

from __future__ import annotations

import logging
import threading
from collections.abc import Mapping
from typing import Any, Protocol

logger = logging.getLogger(__name__)

WIDTH = 16


class Display(Protocol):
    def show(self, line1: str, line2: str) -> None: ...
    def close(self) -> None: ...


def status_lines(values: Mapping[str, float | None], condition: str) -> tuple[str, str]:
    """Line 1: the rating, line 2: the values. Missing values are shown as `--`."""
    temperature = values.get("temperature")
    humidity = values.get("humidity")
    t = "--" if temperature is None else f"{temperature:.0f}C"
    h = "--" if humidity is None else f"{humidity:.0f}%"
    first = "Sensor fault" if condition == "fault" else f"Walk: {condition.upper()}"
    second = f"{t} {h}"
    if len(second) + len(" Tap card") <= WIDTH:
        second += " Tap card"
    return first[:WIDTH], second[:WIDTH]


def pad(text: str) -> str:
    return text[:WIDTH].ljust(WIDTH)


class GroveLcd:
    def __init__(self) -> None:
        from grove.display.jhd1802 import JHD1802  # Pi only

        self._lcd: Any = JHD1802()
        self._lock = threading.Lock()
        self._shown: tuple[str, str] | None = None

    def show(self, line1: str, line2: str) -> None:
        lines = (pad(line1), pad(line2))
        with self._lock:
            if lines == self._shown:
                return
            try:
                for row, text in enumerate(lines):
                    self._lcd.setCursor(row, 0)
                    self._lcd.write(text)
                self._shown = lines
            except OSError as exc:
                logger.warning("LCD write failed: %s", exc)
                self._shown = None

    def close(self) -> None:
        self.show("NatureCheckpoint", "offline")


class LogOnlyDisplay:
    def show(self, line1: str, line2: str) -> None:
        logger.info("LCD | %s | %s", line1, line2)

    def close(self) -> None:
        pass


def create_display(enabled: bool) -> Display:
    if not enabled:
        return LogOnlyDisplay()
    try:
        return GroveLcd()
    except Exception as exc:  # no LCD must not stop the checkpoint
        logger.warning("LCD not available (%s), logging instead", exc)
        return LogOnlyDisplay()
