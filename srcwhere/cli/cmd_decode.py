from srcwhere.base.inputs import IO
from srcwhere.base.options import Spec
from srcwhere.base.text import line, show, table
from srcwhere.smap.loader import load_map

USAGE = "       srcwhere decode MAP [--line N]"
ARGS = ["MAP"]
MAX = 1
SPECS: list[Spec] = [Spec("--line", numeric=True, lo=1, hi=1000000)]


def run_decode(args: list[str], options: dict, io: IO) -> tuple[str, int]:
    """Render a source map's mappings as a table."""
    source_map = load_map(io, args[0])
    selected_line = options.get("--line")

    rows: list[list[str]] = []
    for line_index, segments in enumerate(source_map.lines, start=1):
        if selected_line is not None and line_index != selected_line:
            continue
        for segment in segments:
            if segment.source is None:
                rows.append([str(line_index), str(segment.col + 1), "-", "-", "-", "-"])
                continue

            source = show(source_map.sources[segment.source])
            original_line = str(segment.line + 1)
            original_column = str(segment.column + 1)
            name = "-" if segment.name is None else show(source_map.names[segment.name])
            rows.append(
                [
                    str(line_index),
                    str(segment.col + 1),
                    source,
                    original_line,
                    original_column,
                    name,
                ]
            )

    output = table(["line", "col", "source", "oline", "ocol", "name"], rows)
    return output + line("segments", str(len(rows))), 0
