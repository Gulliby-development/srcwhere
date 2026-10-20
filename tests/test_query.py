import json
from dataclasses import asdict, fields, is_dataclass
from inspect import signature
from typing import get_type_hints

import pytest

from srcwhere.query.lookup import find_segment, source_line
from srcwhere.query.reverse import find_original
from srcwhere.query.stats import Stats, compute_stats
from srcwhere.smap.model import Segment, SourceMap


def _query_map() -> SourceMap:
    return SourceMap(
        None,
        ["a.ts", "a.ts", "b.ts", "unused.ts"],
        ["n", "unused"],
        ["a\r\nb\n", "", None, None],
        [
            [
                Segment(2, 0, 0, 1, None),
                Segment(5, 0, 0, 3, 0),
                Segment(5, 1, 0, 3, None),
                Segment(8, None, None, None, None),
            ],
            [],
            [
                Segment(1, 2, 1, 0, None),
                Segment(4, 1, 0, 3, 0),
                Segment(4, 0, 0, 3, None),
            ],
            [],
        ],
    )


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"))


def _segment_fields(segment: Segment | None) -> list[int | None] | None:
    if segment is None:
        return None
    return [segment.col, segment.source, segment.line, segment.column, segment.name]


def _single_source_map(content: str | None) -> SourceMap:
    return SourceMap(None, ["source.ts"], [], [content], [[]])


@pytest.mark.parametrize(
    ("line", "col", "expected"),
    [
        (0, 0, "null"),
        (0, 2, "[2,0,0,1,null]"),
        (0, 4, "[2,0,0,1,null]"),
        (0, 5, "[5,1,0,3,null]"),
        (0, 7, "[5,1,0,3,null]"),
    ],
)
def test_lookup_exact_preceding_and_equal_columns(line: int, col: int, expected: str) -> None:
    assert _json(_segment_fields(find_segment(_query_map(), line, col))) == expected


@pytest.mark.parametrize(
    ("line", "col", "expected"),
    [
        (0, 8, "null"),
        (0, 99, "null"),
        (1, 0, "null"),
        (4, 0, "null"),
        (2, 99, "[4,0,0,3,null]"),
    ],
)
def test_lookup_barriers_empty_and_nonexistent_lines(line: int, col: int, expected: str) -> None:
    assert _json(_segment_fields(find_segment(_query_map(), line, col))) == expected


@pytest.mark.parametrize(
    ("input_case", "expected"),
    [
        ("[null,0]", "null"),
        ('["",0]', '""'),
        ('["",1]', "null"),
    ],
)
def test_source_line_missing_and_empty_content(input_case: str, expected: str) -> None:
    content, line = json.loads(input_case)
    assert _json(source_line(_single_source_map(content), 0, line)) == expected


@pytest.mark.parametrize(
    ("content", "line", "expected"),
    [
        ("a\r\nb\n", 0, "a"),
        ("a\r\nb\n", 1, "b"),
        ("a\r\nb\n", 2, ""),
        ("a\r\nb\n", 3, None),
        ("a\nb", 1, "b"),
    ],
)
def test_source_line_lf_crlf_and_terminal_empty_line(
    content: str, line: int, expected: str | None
) -> None:
    assert source_line(_single_source_map(content), 0, line) == expected


@pytest.mark.parametrize(
    ("content", "line", "expected"),
    [
        ("a\rb", 0, "a\rb"),
        ("a\r", 0, "a\r"),
        ("a\r\r\n", 0, "a\r"),
    ],
)
def test_source_line_preserves_embedded_terminal_and_extra_cr(
    content: str, line: int, expected: str
) -> None:
    assert source_line(_single_source_map(content), 0, line) == expected


@pytest.mark.parametrize(
    ("source", "line", "col", "expected"),
    [
        ("a.ts", 0, 0, "[null,[]]"),
        ("a.ts", 0, 1, "[1,[[0,2]]]"),
        ("a.ts", 0, 2, "[1,[[0,2]]]"),
    ],
)
def test_reverse_lower_and_best_original_columns(
    source: str, line: int, col: int, expected: str
) -> None:
    assert _json(find_original(_query_map(), source, line, col)) == expected


@pytest.mark.parametrize(
    ("source", "line", "col", "expected"),
    [
        ("a.ts", 0, 3, "[3,[[0,5],[0,5],[2,4],[2,4]]]"),
        ("a.ts", 0, 99, "[3,[[0,5],[0,5],[2,4],[2,4]]]"),
    ],
)
def test_reverse_retains_duplicate_best_matches_in_generated_order(
    source: str, line: int, col: int, expected: str
) -> None:
    assert _json(find_original(_query_map(), source, line, col)) == expected


@pytest.mark.parametrize(
    ("source", "line", "col", "expected"),
    [
        ("a.ts", 1, 99, "[null,[]]"),
        ("b.ts", 1, 0, "[0,[[2,1]]]"),
        ("A.ts", 0, 99, "[null,[]]"),
        ("unused.ts", 0, 99, "[null,[]]"),
    ],
)
def test_reverse_no_match_exact_name_and_distinct_sources(
    source: str, line: int, col: int, expected: str
) -> None:
    assert _json(find_original(_query_map(), source, line, col)) == expected


def test_stats_counts_all_query_map_entries() -> None:
    assert asdict(compute_stats(_query_map())) == {
        "lines": 4,
        "segments": 7,
        "mapped": 6,
        "sources": 4,
        "used": 3,
        "names": 2,
        "named": 2,
        "content": 2,
        "per_source": [3, 2, 1, 0],
    }


def test_stats_empty_and_unmapped_only_maps() -> None:
    assert asdict(compute_stats(SourceMap(None, [], [], [], [[]]))) == {
        "lines": 1,
        "segments": 0,
        "mapped": 0,
        "sources": 0,
        "used": 0,
        "names": 0,
        "named": 0,
        "content": 0,
        "per_source": [],
    }
    assert asdict(
        compute_stats(SourceMap(None, ["a"], ["n"], [""], [[Segment(0, None, None, None, None)]]))
    ) == {
        "lines": 1,
        "segments": 1,
        "mapped": 0,
        "sources": 1,
        "used": 0,
        "names": 1,
        "named": 0,
        "content": 1,
        "per_source": [0],
    }


def test_public_signatures_and_stats_fields_and_mutability() -> None:
    assert list(signature(find_segment).parameters) == ["sm", "line", "col"]
    assert get_type_hints(find_segment) == {
        "sm": SourceMap,
        "line": int,
        "col": int,
        "return": Segment | None,
    }
    assert list(signature(source_line).parameters) == ["sm", "source", "line"]
    assert get_type_hints(source_line) == {
        "sm": SourceMap,
        "source": int,
        "line": int,
        "return": str | None,
    }
    assert list(signature(find_original).parameters) == ["sm", "source", "line", "col"]
    assert get_type_hints(find_original) == {
        "sm": SourceMap,
        "source": str,
        "line": int,
        "col": int,
        "return": tuple[int | None, list[tuple[int, int]]],
    }
    assert list(signature(compute_stats).parameters) == ["sm"]
    assert get_type_hints(compute_stats) == {"sm": SourceMap, "return": Stats}

    assert is_dataclass(Stats)
    assert [field.name for field in fields(Stats)] == [
        "lines",
        "segments",
        "mapped",
        "sources",
        "used",
        "names",
        "named",
        "content",
        "per_source",
    ]
    assert get_type_hints(Stats) == {
        "lines": int,
        "segments": int,
        "mapped": int,
        "sources": int,
        "used": int,
        "names": int,
        "named": int,
        "content": int,
        "per_source": list[int],
    }
    stats = compute_stats(_query_map())
    stats.lines = 99
    stats.per_source.append(7)
    assert stats.lines == 99
    assert stats.per_source == [3, 2, 1, 0, 7]


def test_repeated_queries_return_equal_results_without_mutating_input() -> None:
    sm = _query_map()
    snapshot = SourceMap(
        None,
        ["a.ts", "a.ts", "b.ts", "unused.ts"],
        ["n", "unused"],
        ["a\r\nb\n", "", None, None],
        [
            [
                Segment(2, 0, 0, 1, None),
                Segment(5, 0, 0, 3, 0),
                Segment(5, 1, 0, 3, None),
                Segment(8, None, None, None, None),
            ],
            [],
            [
                Segment(1, 2, 1, 0, None),
                Segment(4, 1, 0, 3, 0),
                Segment(4, 0, 0, 3, None),
            ],
            [],
        ],
    )
    sources = sm.sources
    names = sm.names
    contents = sm.contents
    lines = sm.lines
    first_line = sm.lines[0]
    second_line = sm.lines[1]
    third_line = sm.lines[2]
    fourth_line = sm.lines[3]

    first = (
        find_segment(sm, 0, 5),
        source_line(sm, 0, 1),
        find_original(sm, "a.ts", 0, 3),
        compute_stats(sm),
    )
    second = (
        find_segment(sm, 0, 5),
        source_line(sm, 0, 1),
        find_original(sm, "a.ts", 0, 3),
        compute_stats(sm),
    )

    assert first == second
    assert sm == snapshot
    assert sm.sources is sources
    assert sm.names is names
    assert sm.contents is contents
    assert sm.lines is lines
    assert sm.lines[0] is first_line
    assert sm.lines[1] is second_line
    assert sm.lines[2] is third_line
    assert sm.lines[3] is fourth_line
