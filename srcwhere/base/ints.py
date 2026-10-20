from srcwhere.base.fail import Fail
from srcwhere.base.text import show


def parse_int(name: str, text: str, lo: int, hi: int) -> int:
    """Parse a bounded integer using the command-line grammar."""
    if text == "0":
        value = 0
    else:
        digits = text.removeprefix("-")
        valid_digits = (
            1 <= len(digits) <= 10
            and "1" <= digits[0] <= "9"
            and all("0" <= digit <= "9" for digit in digits[1:])
        )
        if not valid_digits or (text.startswith("-") and digits == "0"):
            raise Fail(f"invalid {name} {show(text)} (expected an integer from {lo} to {hi})")
        value = int(text)

    if not lo <= value <= hi:
        raise Fail(f"invalid {name} {show(text)} (expected an integer from {lo} to {hi})")
    return value


def parse_position(text: str) -> tuple[int, int]:
    """Parse a one-based LINE:COLUMN pair with the required ASCII digit grammar."""
    parts = text.split(":")
    if len(parts) != 2 or any(
        not (1 <= len(part) <= 7 and "1" <= part[0] <= "9")
        or not all("0" <= digit <= "9" for digit in part[1:])
        for part in parts
    ):
        raise Fail(f"invalid position {show(text)} (expected LINE:COLUMN, such as 12:5)")
    return int(parts[0]), int(parts[1])
