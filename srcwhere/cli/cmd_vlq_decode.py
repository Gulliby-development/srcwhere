from srcwhere.base.fail import Fail
from srcwhere.base.inputs import IO
from srcwhere.base.options import Spec
from srcwhere.vlq.stream import decode_numbers

USAGE = "       srcwhere vlq-decode TEXT"
ARGS = ["TEXT"]
MAX = 1
SPECS: list[Spec] = []


def run_vlq_decode(args: list[str], options: dict, io: IO) -> tuple[str, int]:
    """Decode one command-line VLQ stream into decimal numbers."""
    text = args[0]
    if text == "":
        raise Fail("nothing to decode")

    numbers = decode_numbers(text)
    return " ".join(str(number) for number, _ in numbers) + "\n", 0
