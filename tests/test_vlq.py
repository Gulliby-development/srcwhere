import pytest

from srcwhere.base.fail import Fail
from srcwhere.vlq.codec import ALPHABET, encode_number
from srcwhere.vlq.stream import decode_numbers


def test_alphabet_is_the_base64_vlq_alphabet() -> None:
    assert ALPHABET == "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "A"),
        (1, "C"),
        (-1, "D"),
        (16, "gB"),
        (-123456, "hkxH"),
    ],
)
def test_encoder_ordinary_literal_rows(value: int, expected: str) -> None:
    assert encode_number(value) == expected


def test_encoder_inclusive_endpoints() -> None:
    assert encode_number(2147483647) == "+/////D"
    assert encode_number(-2147483647) == "//////D"


def test_decoder_accepts_an_empty_stream() -> None:
    assert decode_numbers("", 0) == []


def test_decoder_preserves_signed_zero() -> None:
    assert decode_numbers("B", 0) == [(0, 1)]


def test_decoder_reads_multiple_numbers_and_their_start_positions() -> None:
    assert decode_numbers("ACDgB", 0) == [(0, 1), (1, 2), (-1, 3), (16, 4)]


def test_decoder_reads_negative_and_endpoint_values() -> None:
    assert decode_numbers("hkxH", 0) == [(-123456, 1)]
    assert decode_numbers("+/////D//////D", 0) == [
        (2147483647, 1),
        (-2147483647, 8),
    ]


def test_decoder_positions_include_the_supplied_offset() -> None:
    assert decode_numbers("gBC", 7) == [(16, 8), (1, 10)]


def test_decoder_accepts_redundant_continuation_groups() -> None:
    assert decode_numbers("ggggggggA", 0) == [(0, 1)]
    assert decode_numbers("hgggggggA", 0) == [(0, 1)]


@pytest.mark.parametrize(
    ("text", "offset", "expected"),
    [
        ("AA!", 0, 'invalid character "!" at character 3'),
        (",", 0, 'invalid character "," at character 1'),
        (";", 0, 'invalid character ";" at character 1'),
        ("Aé", 5, 'invalid character "?" at character 7'),
        ("g!", 3, 'invalid character "!" at character 5'),
    ],
)
def test_decoder_reports_invalid_characters_exactly(text: str, offset: int, expected: str) -> None:
    with pytest.raises(Fail) as error:
        decode_numbers(text, offset)

    assert str(error.value) == expected


@pytest.mark.parametrize(
    ("text", "offset", "expected"),
    [
        ("AAg", 0, "incomplete number at character 3"),
        ("Ag", 9, "incomplete number at character 11"),
        ("gggggggg", 0, "incomplete number at character 1"),
    ],
)
def test_decoder_reports_incomplete_numbers_exactly(text: str, offset: int, expected: str) -> None:
    with pytest.raises(Fail) as error:
        decode_numbers(text, offset)

    assert str(error.value) == expected


@pytest.mark.parametrize(
    ("text", "offset", "expected"),
    [
        ("ggggggE", 0, "number is too large at character 1"),
        ("hgggggE", 0, "number is too large at character 1"),
        ("gggggggB", 0, "number is too large at character 1"),
        ("AgggggggB", 4, "number is too large at character 6"),
    ],
)
def test_decoder_reports_oversized_numbers_exactly(text: str, offset: int, expected: str) -> None:
    with pytest.raises(Fail) as error:
        decode_numbers(text, offset)

    assert str(error.value) == expected
