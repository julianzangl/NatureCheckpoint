"""NFC card reader: M5Stack Unit RFID 2 (WS1850S, MFRC522 register set) on I2C.

The checkpoint reads the UID of a tapped 13.56 MHz card (ISO 14443A: campus cards, key fobs,
NTAG stickers). Only a salted hash of the UID leaves the Pi (`card_hash`), never the UID.

The protocol steps (REQA, anticollision, select per cascade level) follow the MFRC522
datasheet. Frame building and checks are pure functions and are tested without hardware.

Manual test on the Pi: ``python -m nc_sensor.sensors.nfc --bus 1`` prints every tapped UID.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import time
from collections.abc import Callable, Sequence
from typing import Protocol

logger = logging.getLogger(__name__)

DEFAULT_ADDRESS = 0x28

# MFRC522 registers.
COMMAND = 0x01
COM_IRQ = 0x04
DIV_IRQ = 0x05
ERROR = 0x06
FIFO_DATA = 0x09
FIFO_LEVEL = 0x0A
CONTROL = 0x0C
BIT_FRAMING = 0x0D
COLL = 0x0E
MODE = 0x11
TX_CONTROL = 0x14
TX_ASK = 0x15
CRC_RESULT_H = 0x21
CRC_RESULT_L = 0x22
T_MODE = 0x2A
T_PRESCALER = 0x2B
T_RELOAD_H = 0x2C
T_RELOAD_L = 0x2D
VERSION = 0x37

# MFRC522 commands.
IDLE = 0x00
CALC_CRC = 0x03
TRANSCEIVE = 0x0C
SOFT_RESET = 0x0F

# ISO 14443A card commands.
REQA = 0x26
HLTA = 0x50
CASCADE_TAG = 0x88
SELECT_CODES = (0x93, 0x95, 0x97)


class NfcError(RuntimeError):
    """No card answered, or the answer was corrupt."""


class Bus(Protocol):
    def read_byte_data(self, address: int, register: int) -> int: ...
    def write_byte_data(self, address: int, register: int, value: int) -> None: ...


def bcc(uid_part: Sequence[int]) -> int:
    """Block check character: XOR of the four UID bytes of one cascade level."""
    value = 0
    for byte in uid_part:
        value ^= byte
    return value


def check_anticollision(answer: Sequence[int]) -> list[int]:
    """Validate the 5-byte anticollision answer and return its four UID bytes."""
    if len(answer) != 5:
        raise NfcError(f"anticollision answer has {len(answer)} bytes, expected 5")
    if bcc(answer[:4]) != answer[4]:
        raise NfcError("anticollision BCC mismatch")
    return list(answer[:4])


def uid_from_levels(levels: Sequence[Sequence[int]]) -> bytes:
    """Join the UID bytes of all cascade levels, dropping the cascade tags (0x88)."""
    uid: list[int] = []
    for i, part in enumerate(levels):
        more = i < len(levels) - 1
        uid += list(part[1:]) if more and part[0] == CASCADE_TAG else list(part)
    return bytes(uid)


def is_random_uid(uid: bytes) -> bool:
    """ISO 14443-3: a 4-byte UID starting with 0x08 is a random ID, new on every tap.

    Phones (Apple Pay, Google Pay) and many bank cards use it for privacy, so it cannot
    identify a visitor across taps.
    """
    return len(uid) == 4 and uid[0] == 0x08


def card_hash(uid: bytes, salt: str) -> str:
    """Pseudonymous card ID: the backend never sees the raw UID."""
    return hashlib.sha256(salt.encode("utf-8") + uid).hexdigest()[:32]


class Mfrc522:
    """Minimal MFRC522 driver over I2C: enough to read card UIDs."""

    def __init__(
        self,
        bus: Bus,
        address: int = DEFAULT_ADDRESS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.bus = bus
        self.address = address
        self._sleep = sleep

    # --- registers ----------------------------------------------------------------------------

    def _read(self, register: int) -> int:
        return self.bus.read_byte_data(self.address, register)

    def _write(self, register: int, value: int) -> None:
        self.bus.write_byte_data(self.address, register, value)

    def _set_bits(self, register: int, mask: int) -> None:
        self._write(register, self._read(register) | mask)

    def _clear_bits(self, register: int, mask: int) -> None:
        self._write(register, self._read(register) & ~mask & 0xFF)

    # --- setup --------------------------------------------------------------------------------

    def version(self) -> int:
        return self._read(VERSION)

    def init(self) -> None:
        self._write(COMMAND, SOFT_RESET)
        self._sleep(0.05)
        # Timer: auto start, ~25 ms timeout for card answers.
        self._write(T_MODE, 0x80)
        self._write(T_PRESCALER, 0xA9)
        self._write(T_RELOAD_H, 0x03)
        self._write(T_RELOAD_L, 0xE8)
        self._write(TX_ASK, 0x40)  # 100 % ASK modulation
        self._write(MODE, 0x3D)  # CRC preset 0x6363
        self._set_bits(TX_CONTROL, 0x03)  # antenna on

    # --- card communication -------------------------------------------------------------------

    def _transceive(self, data: Sequence[int], tx_last_bits: int = 0) -> list[int]:
        self._write(COMMAND, IDLE)
        self._write(COM_IRQ, 0x7F)
        self._write(FIFO_LEVEL, 0x80)
        for byte in data:
            self._write(FIFO_DATA, byte)
        self._write(BIT_FRAMING, tx_last_bits)
        self._write(COMMAND, TRANSCEIVE)
        self._set_bits(BIT_FRAMING, 0x80)  # start sending
        try:
            for _ in range(50):
                irq = self._read(COM_IRQ)
                if irq & 0x30:  # RxIRq or IdleIRq
                    break
                if irq & 0x01:  # timer: no card
                    raise NfcError("no answer")
                self._sleep(0.001)
            else:
                raise NfcError("no answer")
        finally:
            self._clear_bits(BIT_FRAMING, 0x80)
        if self._read(ERROR) & 0x13:  # buffer overflow, parity or protocol error
            raise NfcError("transfer error")
        return [self._read(FIFO_DATA) for _ in range(self._read(FIFO_LEVEL))]

    def _crc(self, data: Sequence[int]) -> list[int]:
        self._write(COMMAND, IDLE)
        self._write(DIV_IRQ, 0x04)
        self._write(FIFO_LEVEL, 0x80)
        for byte in data:
            self._write(FIFO_DATA, byte)
        self._write(COMMAND, CALC_CRC)
        for _ in range(50):
            if self._read(DIV_IRQ) & 0x04:
                return [self._read(CRC_RESULT_L), self._read(CRC_RESULT_H)]
            self._sleep(0.001)
        raise NfcError("CRC timeout")

    def read_uid(self) -> bytes | None:
        """UID of a card in the field, or None. The card is halted, so it answers once."""
        self._clear_bits(COLL, 0x80)
        try:
            atqa = self._transceive([REQA], tx_last_bits=0x07)
        except NfcError:
            return None
        if len(atqa) != 2:
            return None
        levels: list[list[int]] = []
        for select in SELECT_CODES:
            part = check_anticollision(self._transceive([select, 0x20]))
            frame = [select, 0x70, *part, bcc(part)]
            sak = self._transceive(frame + self._crc(frame))
            levels.append(part)
            if not sak or not sak[0] & 0x04:  # UID complete
                break
        halt = [HLTA, 0x00]
        try:
            self._transceive(halt + self._crc(halt))
        except NfcError:
            pass  # a halted card does not answer; that is the expected outcome
        return uid_from_levels(levels)


class CardReader:
    """Polls one reader and reports each new tap once (debounced per card)."""

    def __init__(self, bus_number: int, address: int = DEFAULT_ADDRESS, debounce_s: float = 3.0):
        self.bus_number = bus_number
        self.address = address
        self.debounce_s = debounce_s
        self._chip: Mfrc522 | None = None
        self._last: tuple[bytes, float] | None = None

    def _open(self) -> Mfrc522:
        from smbus2 import SMBus  # Pi only

        chip = Mfrc522(SMBus(self.bus_number), self.address)
        chip.init()
        logger.info("NFC reader on i2c-%d ready (version 0x%02x)", self.bus_number, chip.version())
        return chip

    def poll(self, now: float) -> bytes | None:
        """Return the UID of a new tap, or None. Never raises."""
        try:
            if self._chip is None:
                self._chip = self._open()
            uid = self._chip.read_uid()
        except (OSError, NfcError) as exc:
            logger.debug("NFC reader on i2c-%d: %s", self.bus_number, exc)
            if isinstance(exc, OSError):
                self._chip = None  # reconnect after an I2C error
            return None
        if uid is None:
            return None
        if self._last and self._last[0] == uid and now - self._last[1] < self.debounce_s:
            return None
        self._last = (uid, now)
        return uid


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Print the UID of every tapped card.")
    parser.add_argument("--bus", type=int, default=1, help="I2C bus number (/dev/i2c-N)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    reader = CardReader(args.bus)
    print(f"Tap a card on the reader on i2c-{args.bus}. Ctrl+C to stop.")
    try:
        while True:
            uid = reader.poll(time.monotonic())
            if uid:
                print(f"card UID: {uid.hex()}", flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
