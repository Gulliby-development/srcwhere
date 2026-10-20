from srcwhere.base.inputs import IO
from srcwhere.base.ints import parse_int
from srcwhere.base.options import Spec
from srcwhere.vlq.codec import encode_number

USAGE = "       srcwhere vlq-encode NUMBER..."
ARGS = ["NUMBER"]
MAX = 20
SPECS: list[Spec] = []


def run_vlq_encode(args: list[str], options: dict, io: IO) -> tuple[str, int]:
    """Encode each validated command-line number as a VLQ value."""
    numbers = [parse_int("number", text, -2147483647, 2147483647) for text in args]
    return "".join(encode_number(number) for number in numbers) + "\n", 0
