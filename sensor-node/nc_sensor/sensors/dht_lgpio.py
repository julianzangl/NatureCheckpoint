"""DHT11/DHT22 single-wire driver on top of lgpio, for the Raspberry Pi 5.

grove.py has no DHT11 module and the RPi.GPIO-based drivers miss edges on the Pi 5. lgpio
timestamps every edge in the kernel, so the 40 data bits can be decoded from pulse lengths.
The decoding is a pure function (`decode`), so it is tested without hardware.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

# A "1" bit is a high pulse of ~70 us, a "0" bit one of ~27 us.
ONE_THRESHOLD_US = 50.0
START_LOW_S = 0.02
LISTEN_S = 0.05


class DhtError(RuntimeError):
    """A single read failed (too few edges or a bad checksum)."""


def bits_to_bytes(pulses_us: Sequence[float]) -> list[int]:
    if len(pulses_us) < 40:
        raise DhtError(f"only {len(pulses_us)} of 40 bits received")
    data = [0] * 5
    # The 40 data bits are the last high pulses; anything before is the sensor's response.
    for i, pulse in enumerate(pulses_us[-40:]):
        data[i // 8] = (data[i // 8] << 1) | (1 if pulse > ONE_THRESHOLD_US else 0)
    return data


def decode(pulses_us: Sequence[float], dht_type: str = "11") -> tuple[float, float]:
    """Return (humidity %, temperature °C) from the high-pulse lengths of one transfer."""
    data = bits_to_bytes(pulses_us)
    if (data[0] + data[1] + data[2] + data[3]) & 0xFF != data[4]:
        raise DhtError("checksum mismatch")
    if dht_type == "22":
        humidity = ((data[0] << 8) | data[1]) / 10
        temperature = (((data[2] & 0x7F) << 8) | data[3]) / 10
        negative = bool(data[2] & 0x80)
    else:
        humidity = data[0] + data[1] / 10
        temperature = data[2] + (data[3] & 0x7F) / 10
        negative = bool(data[3] & 0x80)
    return humidity, -temperature if negative else temperature


def high_pulses(edges: Sequence[tuple[int, int]]) -> list[float]:
    """Length in microseconds of every high pulse, from (level, tick_ns) edge events."""
    pulses = []
    for (level_a, tick_a), (level_b, tick_b) in zip(edges, edges[1:], strict=False):
        if level_a == 1 and level_b == 0:
            pulses.append((tick_b - tick_a) / 1000)
    return pulses


class LgpioDht:
    """Reads one DHT sensor; ``read()`` raises `DhtError` when a transfer is incomplete."""

    def __init__(self, dht_type: str, pin: int, chip: int = 0) -> None:
        import lgpio  # Pi only

        self._lgpio: Any = lgpio
        self.dht_type = dht_type
        self.pin = pin
        self._edges: list[tuple[int, int]] = []
        self._handle = lgpio.gpiochip_open(chip)
        lgpio.gpio_claim_alert(self._handle, pin, lgpio.BOTH_EDGES, lgpio.SET_PULL_UP)
        self._callback = lgpio.callback(self._handle, pin, lgpio.BOTH_EDGES, self._on_edge)

    def _on_edge(self, chip: int, gpio: int, level: int, tick: int) -> None:
        if level in (0, 1):
            self._edges.append((level, tick))

    def read(self) -> tuple[float, float]:
        lg = self._lgpio
        self._edges.clear()
        # Start signal: pull the line low, then release it and record the answer.
        lg.gpio_claim_output(self._handle, self.pin, 0)
        time.sleep(START_LOW_S)
        lg.gpio_claim_alert(self._handle, self.pin, lg.BOTH_EDGES, lg.SET_PULL_UP)
        time.sleep(LISTEN_S)
        return decode(high_pulses(list(self._edges)), self.dht_type)

    def close(self) -> None:
        self._callback.cancel()
        self._lgpio.gpiochip_close(self._handle)
