from srcwhere.base.inputs import IO
from srcwhere.base.options import Spec
from srcwhere.base.text import plural
from srcwhere.smap.loader import load_problems

USAGE = "usage: srcwhere check MAP"
ARGS = ["MAP"]
MAX = 1
SPECS: list[Spec] = []


def run_check(args: list[str], options: dict, io: IO) -> tuple[str, int]:
    """Validate one source map and report all of its structural problems."""
    _, problems, source_map = load_problems(io, args[0])
    if problems:
        details = "".join(f"{problem.format()}\n" for problem in problems)
        return details + plural(len(problems), "problem") + "\n", 1

    segment_count = sum(len(line) for line in source_map.lines)
    return f"ok, {plural(segment_count, 'segment')}\n", 0
