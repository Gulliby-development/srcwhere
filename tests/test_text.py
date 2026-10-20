import pytest

from srcwhere.base.fail import Fail
from srcwhere.base.ints import parse_int, parse_position
from srcwhere.base.text import line, plural, show, table


def test_fail_preserves_its_message() -> None:
    error = Fail("bad input")

    assert str(error) == "bad input"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", '""'),
        ("A ~", '"A ~"'),
        ("a\n\t\x7fé😀", '"a?????"'),
        ('"\\', '""\\"'),
    ],
)
def test_show_literal_contract_rows(text: str, expected: str) -> None:
    assert show(text) == expected


def test_show_ascii_boundaries_and_non_ascii_code_points() -> None:
    assert show("\x1f \x7e\x7f") == '"? ~?"'
    assert show("é😀") == '"??"'


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("segments", "3", "segments    3\n"),
        ("abcdefghijk", "x", "abcdefghijk  x\n"),
        ("", "", "            \n"),
    ],
)
def test_line_literal_contract_rows(key: str, value: str, expected: str) -> None:
    assert line(key, value) == expected


def test_table_literal_contract_rows() -> None:
    assert table(["name", "n"], [["a", "12"], ["longer", ""]]) == (
        "name    n\na       12\nlonger\n"
    )
    assert table(["line", "col"], []) == "line  col\n"


def test_table_keeps_short_rows_left_aligned_without_trailing_spaces() -> None:
    assert table(["x", "long"], [["a"]]) == "x  long\na\n"


@pytest.mark.parametrize(
    ("count", "word", "expected"),
    [
        (1, "problem", "1 problem"),
        (0, "problem", "0 problems"),
        (2, "problem", "2 problems"),
    ],
)
def test_plural_literal_contract_rows(count: int, word: str, expected: str) -> None:
    assert plural(count, word) == expected


def test_parse_int_accepts_zero_and_inclusive_endpoints() -> None:
    assert parse_int("number", "0", -2147483647, 2147483647) == 0
    assert parse_int("number", "-2147483647", -2147483647, 2147483647) == -2147483647
    assert parse_int("number", "2147483647", -2147483647, 2147483647) == 2147483647


@pytest.mark.parametrize(
    ("name", "text", "lo", "hi", "expected"),
    [
        ("n", "-0", -9, 9, 'invalid n "-0" (expected an integer from -9 to 9)'),
        ("n", "+3", -9, 9, 'invalid n "+3" (expected an integer from -9 to 9)'),
        ("n", "007", -9, 9, 'invalid n "007" (expected an integer from -9 to 9)'),
        ("n", "1.5", -9, 9, 'invalid n "1.5" (expected an integer from -9 to 9)'),
        ("n", "", -9, 9, 'invalid n "" (expected an integer from -9 to 9)'),
        ("n", " 1", -9, 9, 'invalid n " 1" (expected an integer from -9 to 9)'),
        ("n", "١", -9, 9, 'invalid n "?" (expected an integer from -9 to 9)'),
        (
            "n",
            "10000000000",
            0,
            10000000000,
            'invalid n "10000000000" (expected an integer from 0 to 10000000000)',
        ),
        (
            "--line",
            "0",
            1,
            1000000,
            'invalid --line "0" (expected an integer from 1 to 1000000)',
        ),
        ("n", "10", -9, 9, 'invalid n "10" (expected an integer from -9 to 9)'),
        ("n", "-10", -9, 9, 'invalid n "-10" (expected an integer from -9 to 9)'),
    ],
)
def test_parse_int_rejects_invalid_grammar_and_ranges(
    name: str, text: str, lo: int, hi: int, expected: str
) -> None:
    with pytest.raises(Fail) as error:
        parse_int(name, text, lo, hi)

    assert str(error.value) == expected


def test_parse_position_accepts_literal_valid_rows() -> None:
    assert parse_position("12:5") == (12, 5)
    assert parse_position("1:9999999") == (1, 9999999)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0:1", 'invalid position "0:1" (expected LINE:COLUMN, such as 12:5)'),
        ("1", 'invalid position "1" (expected LINE:COLUMN, such as 12:5)'),
        ("1:2:3", 'invalid position "1:2:3" (expected LINE:COLUMN, such as 12:5)'),
        ("01:2", 'invalid position "01:2" (expected LINE:COLUMN, such as 12:5)'),
        (
            "10000000:1",
            'invalid position "10000000:1" (expected LINE:COLUMN, such as 12:5)',
        ),
        ("1:٢", 'invalid position "1:?" (expected LINE:COLUMN, such as 12:5)'),
        ("1:0", 'invalid position "1:0" (expected LINE:COLUMN, such as 12:5)'),
        (":1", 'invalid position ":1" (expected LINE:COLUMN, such as 12:5)'),
        ("1:", 'invalid position "1:" (expected LINE:COLUMN, such as 12:5)'),
    ],
)
def test_parse_position_rejects_invalid_literal_rows(text: str, expected: str) -> None:
    with pytest.raises(Fail) as error:
        parse_position(text)

    assert str(error.value) == expected
