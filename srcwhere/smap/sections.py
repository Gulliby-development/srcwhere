from srcwhere.smap.model import Segment, SourceMap


def merge(file: str | None, parts: list[tuple[int, int, SourceMap]]) -> SourceMap:
    sources: list[str] = []
    names: list[str] = []
    contents: list[str | None] = []
    line_count = 1

    for line_offset, _, sm in parts:
        sources.extend(sm.sources)
        names.extend(sm.names)
        contents.extend(sm.contents)
        line_count = max(line_count, line_offset + len(sm.lines))

    lines: list[list[Segment]] = [[] for _ in range(line_count)]
    source_offset = 0
    name_offset = 0

    for line_offset, column_offset, sm in parts:
        for index, section_line in enumerate(sm.lines):
            generated_line = line_offset + index
            for segment in section_line:
                generated_column = segment.col + (column_offset if index == 0 else 0)
                source = segment.source + source_offset if segment.source is not None else None
                name = segment.name + name_offset if segment.name is not None else None
                lines[generated_line].append(
                    Segment(
                        generated_column,
                        source,
                        segment.line,
                        segment.column,
                        name,
                    )
                )
        source_offset += len(sm.sources)
        name_offset += len(sm.names)

    for generated_line in lines:
        generated_line.sort(key=lambda segment: segment.col)

    return SourceMap(file, sources, names, contents, lines)
