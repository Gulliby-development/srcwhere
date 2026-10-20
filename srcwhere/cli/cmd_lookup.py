from srcwhere.base.inputs import IO
from srcwhere.base.ints import parse_position
from srcwhere.base.options import Spec
from srcwhere.base.text import line, show
from srcwhere.query.lookup import find_segment, source_line
from srcwhere.smap.loader import load_map

USAGE = "       srcwhere lookup MAP LINE:COL"
ARGS = ["MAP", "POSITION"]
MAX = 2
SPECS: list[Spec] = []


def run_lookup(args: list[str], options: dict, io: IO) -> tuple[str, int]:
    """Find and format the mapped source position for a generated position."""
    source_map = load_map(io, args[0])
    position = args[1]
    generated_line, generated_column = parse_position(position)
    segment = find_segment(source_map, generated_line - 1, generated_column - 1)

    output = line("generated", position)
    if segment is None:
        return output + line("result", "unmapped"), 1

    source_index = segment.source
    original_line = segment.line
    original_column = segment.column
    output += line("segment", f"{generated_line}:{segment.col + 1}")
    output += line("source", show(source_map.sources[source_index]))
    output += line("original", f"{original_line + 1}:{original_column + 1}")

    if segment.name is not None:
        output += line("name", show(source_map.names[segment.name]))

    content_line = source_line(source_map, source_index, original_line)
    if content_line is not None:
        output += line("text", show(content_line))

    return output, 0
