from srcwhere.smap.model import Segment, SourceMap


def find_segment(sm: SourceMap, line: int, col: int) -> Segment | None:
    if line < 0 or line >= len(sm.lines):
        return None

    winner: Segment | None = None
    for segment in sm.lines[line]:
        if segment.col > col:
            break
        winner = segment

    if winner is None or winner.source is None:
        return None
    return winner


def source_line(sm: SourceMap, source: int, line: int) -> str | None:
    if source < 0 or source >= len(sm.contents) or line < 0:
        return None

    content = sm.contents[source]
    if content is None:
        return None

    lines = content.split("\n")
    if line >= len(lines):
        return None

    result = lines[line]
    if line < len(lines) - 1 and result.endswith("\r"):
        return result[:-1]
    return result
