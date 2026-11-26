import pytest

from nc_sensor.sensors.nfc import (
    CardReader,
    NfcError,
    bcc,
    card_hash,
    check_anticollision,
    is_random_uid,
    uid_from_levels,
)

UID4 = [0xDE, 0xAD, 0xBE, 0xEF]


def test_bcc_is_xor_of_the_bytes() -> None:
    assert bcc(UID4) == 0xDE ^ 0xAD ^ 0xBE ^ 0xEF
    assert bcc([]) == 0


def test_anticollision_answer_returns_uid_bytes() -> None:
    assert check_anticollision([*UID4, bcc(UID4)]) == UID4


def test_anticollision_bcc_mismatch_raises() -> None:
    with pytest.raises(NfcError, match="BCC"):
        check_anticollision([*UID4, bcc(UID4) ^ 0xFF])


@pytest.mark.parametrize("answer", [UID4, [*UID4, bcc(UID4), 0x00], []])
def test_anticollision_wrong_length_raises(answer: list[int]) -> None:
    with pytest.raises(NfcError, match="expected 5"):
        check_anticollision(answer)


def test_single_level_uid_has_four_bytes() -> None:
    assert uid_from_levels([UID4]) == bytes(UID4)


def test_double_level_uid_drops_the_cascade_tag() -> None:
    levels = [[0x88, 0x04, 0x11, 0x22], [0x33, 0x44, 0x55, 0x66]]

    assert uid_from_levels(levels) == bytes([0x04, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66])


def test_card_hash_is_deterministic_and_salted() -> None:
    uid = bytes(UID4)
    first = card_hash(uid, "salt-a")

    assert first == card_hash(uid, "salt-a")
    assert first != card_hash(uid, "salt-b")
    assert first != card_hash(bytes([0x01, 0x02, 0x03, 0x04]), "salt-a")


def test_card_hash_is_32_hex_chars_without_the_uid() -> None:
    uid = bytes(UID4)
    value = card_hash(uid, "salt")

    assert len(value) == 32
    assert int(value, 16) >= 0
    assert uid.hex() not in value


# --- debounced polling --------------------------------------------------------------------------


class FakeChip:
    """Returns queued read_uid results; an exception in the queue is raised instead."""

    def __init__(self, results: list[object]) -> None:
        self.results = results

    def read_uid(self) -> bytes | None:
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result  # type: ignore[return-value]


def reader_with(monkeypatch, results: list[object]) -> tuple[CardReader, list[int]]:
    reader = CardReader(bus_number=1, debounce_s=3.0)
    chip = FakeChip(results)
    opened: list[int] = []

    def fake_open() -> FakeChip:
        opened.append(1)
        return chip

    monkeypatch.setattr(reader, "_open", fake_open)
    return reader, opened


CARD_A = b"\x01\x02\x03\x04"
CARD_B = b"\x05\x06\x07\x08"


def test_first_tap_is_reported(monkeypatch) -> None:
    reader, _ = reader_with(monkeypatch, [CARD_A])

    assert reader.poll(0.0) == CARD_A


def test_no_card_returns_none(monkeypatch) -> None:
    reader, _ = reader_with(monkeypatch, [None])

    assert reader.poll(0.0) is None


def test_same_card_within_debounce_is_ignored(monkeypatch) -> None:
    reader, _ = reader_with(monkeypatch, [CARD_A, CARD_A, CARD_A])

    assert reader.poll(0.0) == CARD_A
    assert reader.poll(2.9) is None
    assert reader.poll(3.0) == CARD_A


def test_other_card_is_reported_immediately(monkeypatch) -> None:
    reader, _ = reader_with(monkeypatch, [CARD_A, CARD_B])

    assert reader.poll(0.0) == CARD_A
    assert reader.poll(0.5) == CARD_B


def test_os_error_returns_none_and_reconnects(monkeypatch) -> None:
    reader, opened = reader_with(monkeypatch, [OSError("i2c gone"), CARD_A])

    assert reader.poll(0.0) is None
    assert reader.poll(1.0) == CARD_A
    assert len(opened) == 2


def test_nfc_error_keeps_the_connection(monkeypatch) -> None:
    reader, opened = reader_with(monkeypatch, [NfcError("corrupt"), CARD_A])

    assert reader.poll(0.0) is None
    assert reader.poll(1.0) == CARD_A
    assert len(opened) == 1


def test_open_failure_returns_none(monkeypatch) -> None:
    reader = CardReader(bus_number=3)

    def broken_open() -> FakeChip:
        raise OSError("no such bus")

    monkeypatch.setattr(reader, "_open", broken_open)

    assert reader.poll(0.0) is None


@pytest.mark.parametrize(
    ("uid", "expected"),
    [
        (bytes.fromhex("08a1b2c3"), True),  # random ID of a phone or bank card
        (bytes.fromhex("04a1b2c3"), False),
        (bytes.fromhex("08a1b2c3d4e5f6"), False),  # 7-byte UIDs are never random IDs
    ],
)
def test_is_random_uid(uid, expected):
    assert is_random_uid(uid) is expected
