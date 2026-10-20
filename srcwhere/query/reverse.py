from srcwhere.smap.model import SourceMap


def find_original(
    sm: SourceMap, source: str, line: int, col: int
) -> tuple[int | None, list[tuple[int, int]]]:
    best_column: int | None = None
    matches: list[tuple[int, int]] = []

    for generated_line, segments in enumerate(sm.lines):
        for segment in segments:
            if segment.source is None:
                continue
            if sm.sources[segment.source] != source or segment.line != line:
                continue
            if segment.column is None or segment.column > col:
                continue

            if best_column is None or segment.column > best_column:
                best_column = segment.column
                matches = [(generated_line, segment.col)]
            elif segment.column == best_column:
                matches.append((generated_line, segment.col))

    return best_column, matches
