from srcwhere.base.fail import Fail
from srcwhere.base.inputs import IO, read_text
from srcwhere.base.options import Spec
from srcwhere.smap.loader import load_map
from srcwhere.trace.remap import remap_trace

USAGE = "       srcwhere symbolize MAP TRACE [--file NAME]"
ARGS = ["MAP", "TRACE"]
MAX = 2
SPECS = [Spec("--file")]


def run_symbolize(args: list[str], options: dict, io: IO) -> tuple[str, int]:
    """Remap matching frames from a trace using the named source map."""
    map_arg, trace_arg = args
    if map_arg == "-" and trace_arg == "-":
        raise Fail("only one argument can be -")

    source_map = load_map(io, map_arg)
    name = options.get("--file")
    if name is None:
        if source_map.file is None:
            raise Fail('the map has no "file" (give --file NAME)')
        name = source_map.file.rsplit("/", 1)[-1]

    _, text = read_text(io, trace_arg)
    rewritten, unmapped = remap_trace(source_map, text, name)
    return rewritten, 1 if unmapped > 0 else 0
