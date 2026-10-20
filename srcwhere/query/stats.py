from dataclasses import dataclass

from srcwhere.smap.model import SourceMap


@dataclass
class Stats:
    lines: int
    segments: int
    mapped: int
    sources: int
    used: int
    names: int
    named: int
    content: int
    per_source: list[int]


def compute_stats(sm: SourceMap) -> Stats:
    per_source = [0] * len(sm.sources)
    segments = 0
    mapped = 0
    named = 0
    used_sources: set[int] = set()

    for generated_line in sm.lines:
        for segment in generated_line:
            segments += 1
            if segment.source is not None:
                mapped += 1
                used_sources.add(segment.source)
                per_source[segment.source] += 1
            if segment.name is not None:
                named += 1

    return Stats(
        lines=len(sm.lines),
        segments=segments,
        mapped=mapped,
        sources=len(sm.sources),
        used=len(used_sources),
        names=len(sm.names),
        named=named,
        content=sum(content is not None for content in sm.contents),
        per_source=per_source,
    )
