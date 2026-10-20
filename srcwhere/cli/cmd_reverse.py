from srcwhere.base.fail import Fail
from srcwhere.base.inputs import IO
from srcwhere.base.ints import parse_position
from srcwhere.base.options import Spec
from srcwhere.base.text import line, show
from srcwhere.query.reverse import find_original
from srcwhere.smap.loader import load_map

USAGE = "       srcwhere reverse MAP SOURCE LINE:COL"
ARGS = ["MAP", "SOURCE", "POSITION"]
MAX = 3
SPECS: list[Spec] = []


def run_reverse(args: list[str], options: dict, io: IO) -> tuple[str, int]:
    """Find and format generated positions for an original source position."""
    source_map = load_map(io, args[0])
    source = args[1]
    if source not in source_map.sources:
        raise Fail(f"no source named {show(source)}")

    position = args[2]
    original_line, original_column = parse_position(position)
    best_column, matches = find_original(source_map, source, original_line - 1, original_column - 1)

    output = line("original", position)
    if best_column is None:
        return output + line("result", "unmapped"), 1

    output += line("segment", f"{original_line}:{best_column + 1}")
    output += line("matches", str(len(matches)))
    for generated_line, generated_column in matches:
        output += line("generated", f"{generated_line + 1}:{generated_column + 1}")

    return output, 0
