import pytest

from nc_sensor.sensors.dht_lgpio import DhtError, bits_to_bytes, decode, high_pulses

ZERO_US = 27.0
ONE_US = 70.0


def pulses(data: list[int], leading: int = 0) -> list[float]:
    """High-pulse lengths for five data bytes, MSB first, after `leading` response pulses."""
    bits = [ONE_US if byte >> (7 - i) & 1 else ZERO_US for byte in data for i in range(8)]
    return [80.0] * leading + bits


def with_checksum(*data: int) -> list[int]:
    return [*data, sum(data) & 0xFF]


def test_bits_to_bytes_round_trip() -> None:
    data = [0x12, 0x34, 0x56, 0x78, 0x9A]

    assert bits_to_bytes(pulses(data)) == data


def test_only_the_last_40_pulses_are_data() -> None:
    # The sensor's response pulse(s) come before the data and must be skipped.
    data = with_checksum(55, 0, 23, 4)

    assert bits_to_bytes(pulses(data, leading=3)) == data


def test_too_few_bits_raise() -> None:
    with pytest.raises(DhtError, match="39 of 40"):
        bits_to_bytes(pulses(with_checksum(55, 0, 23, 4))[1:])


def test_dht11_decodes_integer_and_tenths() -> None:
    assert decode(pulses(with_checksum(55, 0, 23, 4), leading=1), "11") == (55.0, 23.4)


def test_dht11_negative_temperature() -> None:
    # DHT11 marks a negative temperature with the top bit of the decimal byte.
    assert decode(pulses(with_checksum(80, 0, 1, 0x85)), "11") == (80.0, -1.5)


def test_dht22_decodes_16_bit_values() -> None:
    # 65.2 % = 0x028C, 23.5 °C = 0x00EB
    assert decode(pulses(with_checksum(0x02, 0x8C, 0x00, 0xEB)), "22") == (65.2, 23.5)


def test_dht22_negative_temperature() -> None:
    # -10.1 °C: sign bit in the high temperature byte, 101 = 0x65
    assert decode(pulses(with_checksum(0x02, 0x8C, 0x80, 0x65)), "22") == (65.2, -10.1)


def test_checksum_mismatch_raises() -> None:
    data = with_checksum(55, 0, 23, 4)
    data[4] ^= 0x01

    with pytest.raises(DhtError, match="checksum"):
        decode(pulses(data), "11")


def test_high_pulses_measures_rising_to_falling_edges() -> None:
    edges = [(1, 0), (0, 27_000), (1, 50_000), (0, 120_000), (0, 130_000), (1, 140_000)]

    assert high_pulses(edges) == [27.0, 70.0]


def test_high_pulses_of_no_edges_is_empty() -> None:
    assert high_pulses([]) == []
