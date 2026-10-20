from srcwhere.base.fail import Fail
from srcwhere.base.text import show
from srcwhere.vlq.codec import ALPHABET

_MAX_MAGNITUDE = 2147483647


def decode_numbers(text: str, offset: int = 0) -> list[tuple[int, int]]:
    """Decode signed base64 VLQ numbers with one-based start positions."""
    numbers: list[tuple[int, int]] = []
    active = False
    start = 0
    negative = False
    magnitude = 0
    magnitude_shift = 0
    overflow = False

    for index, character in enumerate(text):
        digit = ALPHABET.find(character)
        position = offset + index + 1
        if digit < 0:
            raise Fail(f"invalid character {show(character)} at character {position}")

        if not active:
            start = position
            negative = bool(digit & 1)
            magnitude = (digit & 31) >> 1
            magnitude_shift = 4
            overflow = False
        else:
            payload = digit & 31
            if payload and not overflow:
                if magnitude_shift >= 31 or payload > (
                    (_MAX_MAGNITUDE - magnitude) >> magnitude_shift
                ):
                    overflow = True
                else:
                    magnitude += payload << magnitude_shift
            magnitude_shift += 5

        if digit & 32:
            active = True
        else:
            if overflow:
                raise Fail(f"number is too large at character {start}")
            value = -magnitude if negative else magnitude
            numbers.append((value, start))
            active = False

    if active:
        raise Fail(f"incomplete number at character {start}")

    return numbers
