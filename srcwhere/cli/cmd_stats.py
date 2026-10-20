from srcwhere.base.inputs import IO
from srcwhere.base.options import Spec
from srcwhere.base.text import line, show
from srcwhere.query.stats import compute_stats
from srcwhere.smap.loader import load_map

USAGE = "       srcwhere stats MAP"
ARGS = ["MAP"]
MAX = 1
SPECS: list[Spec] = []


def run_stats(args: list[str], options: dict, io: IO) -> tuple[str, int]:
    """Render aggregate and per-source statistics for a source map."""
    source_map = load_map(io, args[0])
    stats = compute_stats(source_map)

    output = ""
    for label in ("lines", "segments", "mapped", "sources", "used", "names", "named", "content"):
        output += line(label, str(getattr(stats, label)))
    for name, count in zip(source_map.sources, stats.per_source):
        output += line("source", f"{show(name)} {count}")

    return output, 0
