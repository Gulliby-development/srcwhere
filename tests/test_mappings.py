import json
from dataclasses import FrozenInstanceError, fields
from typing import get_type_hints

import pytest

from srcwhere.smap.mappings import decode_mappings
from srcwhere.smap.model import Problem, Segment, SourceMap
from srcwhere.smap.sections import merge


def _serialize_decode_result(
    result: tuple[list[list[Segment]], Problem | None],
) -> str:
    lines, problem = result
    serialized_lines = [
        [
            [segment.col, segment.source, segment.line, segment.column, segment.name]
            for segment in line
        ]
        for line in lines
    ]
    message = problem.format() if problem is not None else None
    return json.dumps([serialized_lines, message], separators=(",", ":"))


def test_model_fields_annotations_equality_and_mutability() -> None:
    assert [field.name for field in fields(Segment)] == [
        "col",
        "source",
        "line",
        "column",
        "name",
    ]
    assert get_type_hints(Segment) == {
        "col": int,
        "source": int | None,
        "line": int | None,
        "column": int | None,
        "name": int | None,
    }
    assert [field.name for field in fields(SourceMap)] == [
        "file",
        "sources",
        "names",
        "contents",
        "lines",
    ]
    assert get_type_hints(SourceMap) == {
        "file": str | None,
        "sources": list[str],
        "names": list[str],
        "contents": list[str | None],
        "lines": list[list[Segment]],
    }
    assert [field.name for field in fields(Problem)] == ["code", "text"]
    assert get_type_hints(Problem) == {"code": str, "text": str}

    mapped = Segment(0, 0, 0, 0, None)
    assert mapped == Segment(0, 0, 0, 0, None)
    assert Segment(0, None, None, None, None) == Segment(0, None, None, None, None)
    with pytest.raises(FrozenInstanceError):
        mapped.col = 1

    problem = Problem("SM101", "invalid")
    with pytest.raises(FrozenInstanceError):
        problem.code = "SM102"

    sources = ["a.ts"]
    names = ["main"]
    contents = [None]
    lines = [[mapped]]
    source_map = SourceMap("bundle.js", sources, names, contents, lines)
    assert source_map == SourceMap("bundle.js", ["a.ts"], ["main"], [None], [[mapped]])
    assert source_map.sources is sources
    assert source_map.names is names
    assert source_map.contents is contents
    assert source_map.lines is lines
    source_map.file = None
    assert source_map.file is None


@pytest.mark.parametrize(
    ("code", "text", "expected"),
    [
        (
            "SM101",
            'invalid character "!" at character 4',
            'SM101 invalid character "!" at character 4',
        ),
        (
            "SM104",
            "generated column -1 is negative at character 1",
            "SM104 generated column -1 is negative at character 1",
        ),
    ],
)
def test_problem_format_literal_rows(code: str, text: str, expected: str) -> None:
    assert Problem(code, text).format() == expected


@pytest.mark.parametrize(
    ("input_case", "expected"),
    [
        ('["",0,0]', "[[[]],null]"),
        ('[";,;",0,0]', "[[[],[],[]],null]"),
        (
            '["A,A,C",0,0]',
            "[[[[0,null,null,null,null],[0,null,null,null,null],[1,null,null,null,null]]],null]",
        ),
    ],
)
def test_decode_empty_segments_and_equal_columns(input_case: str, expected: str) -> None:
    text, nsources, nnames = json.loads(input_case)
    assert _serialize_decode_result(decode_mappings(text, nsources, nnames)) == expected


@pytest.mark.parametrize(
    ("input_case", "expected"),
    [
        (
            '["AAAA,AAAAB",1,1]',
            "[[[[0,0,0,0,null],[0,0,0,0,0]]],null]",
        ),
        (
            '["CCCCC,C,CAAA;AAAAA",2,2]',
            "[[[[1,1,1,1,1],[2,null,null,null,null],[3,1,1,1,null]],[[0,1,1,1,1]]],null]",
        ),
        (
            '["CCCCE;ADDDD",2,3]',
            "[[[[1,1,1,1,2]],[[0,0,0,0,1]]],null]",
        ),
        (
            '["+/////D",0,0]',
            "[[[[2147483647,null,null,null,null]]],null]",
        ),
    ],
)
def test_decode_mapped_fields_persistent_deltas_and_maximum(input_case: str, expected: str) -> None:
    text, nsources, nnames = json.loads(input_case)
    assert _serialize_decode_result(decode_mappings(text, nsources, nnames)) == expected


@pytest.mark.parametrize(
    ("input_case", "expected"),
    [
        ('["AAA!",2,1]', '[[],"SM101 invalid character \\"!\\" at character 4"]'),
        ('["AAAAg",2,1]', '[[],"SM102 incomplete number at character 5"]'),
        (
            '["AAAA;AA",2,1]',
            '[[[[0,0,0,0,null]]],"SM103 segment has 2 fields (expected 1, 4 or 5) at character 6"]',
        ),
        ('["D",2,1]', '[[],"SM104 generated column -1 is negative at character 1"]'),
        (
            '["AEAA",2,1]',
            '[[],"SM105 source index 2 is out of range (sources has 2) at character 2"]',
        ),
        ('["AADA",2,1]', '[[],"SM106 original line -1 is negative at character 3"]'),
        ('["AACD",2,1]', '[[],"SM107 original column -1 is negative at character 4"]'),
        (
            '["AAAAC",2,1]',
            '[[],"SM108 name index 1 is out of range (names has 1) at character 5"]',
        ),
        (
            '["AAAA,GAAA,DAAA",2,1]',
            (
                '[[],"SM110 generated column 2 is before column 3 of the previous segment '
                'at character 11"]'
            ),
        ),
        ('["AgggggggBAA",2,1]', '[[],"SM111 number is too large at character 2"]'),
        (
            '["ADAA",2,1]',
            '[[],"SM105 source index -1 is out of range (sources has 2) at character 2"]',
        ),
        (
            '["AAAAD",2,1]',
            '[[],"SM108 name index -1 is out of range (names has 1) at character 5"]',
        ),
    ],
)
def test_decode_reports_each_diagnostic_exactly(input_case: str, expected: str) -> None:
    text, nsources, nnames = json.loads(input_case)
    assert _serialize_decode_result(decode_mappings(text, nsources, nnames)) == expected


@pytest.mark.parametrize(
    ("input_case", "expected"),
    [
        ('["DA!",1,1]', '[[],"SM101 invalid character \\"!\\" at character 3"]'),
        ('["Dg",1,1]', '[[],"SM102 incomplete number at character 2"]'),
        (
            '["DA",1,1]',
            '[[],"SM103 segment has 2 fields (expected 1, 4 or 5) at character 1"]',
        ),
        (
            '["DDDDD",1,1]',
            '[[],"SM104 generated column -1 is negative at character 1"]',
        ),
        (
            '["ADDDD",1,1]',
            '[[],"SM105 source index -1 is out of range (sources has 1) at character 2"]',
        ),
        (
            '["AADDD",1,1]',
            '[[],"SM106 original line -1 is negative at character 3"]',
        ),
        (
            '["AAADD",1,1]',
            '[[],"SM107 original column -1 is negative at character 4"]',
        ),
    ],
)
def test_decode_competing_errors_follow_required_precedence(input_case: str, expected: str) -> None:
    text, nsources, nnames = json.loads(input_case)
    assert _serialize_decode_result(decode_mappings(text, nsources, nnames)) == expected


@pytest.mark.parametrize(
    ("input_case", "expected"),
    [
        (
            '["AAAA;;,A,AA;!",1,1]',
            '[[[[0,0,0,0,null]],[]],"SM103 segment has 2 fields (expected 1, 4 or 5) at character 10"]',
        ),
        (
            '["A;AAé",0,0]',
            '[[[[0,null,null,null,null]]],"SM101 invalid character \\"?\\" at character 5"]',
        ),
    ],
)
def test_decode_keeps_completed_lines_and_uses_absolute_code_point_positions(
    input_case: str, expected: str
) -> None:
    text, nsources, nnames = json.loads(input_case)
    assert _serialize_decode_result(decode_mappings(text, nsources, nnames)) == expected


def test_merge_without_parts_returns_one_empty_line() -> None:
    assert merge(None, []) == SourceMap(None, [], [], [], [[]])


def test_merge_combines_overlapping_offsets_and_only_offsets_first_line_columns() -> None:
    first = SourceMap(
        "first.js",
        ["a.ts"],
        [],
        [None],
        [
            [Segment(0, 0, 0, 0, None), Segment(5, 0, 1, 0, None)],
            [],
        ],
    )
    second = SourceMap(
        "second.js",
        ["b.ts"],
        [],
        ["b"],
        [
            [Segment(0, 0, 0, 0, None)],
            [Segment(1, 0, 0, 1, None)],
        ],
    )

    assert merge("all.js", [(0, 0, first), (0, 10, second)]) == SourceMap(
        "all.js",
        ["a.ts", "b.ts"],
        [],
        [None, "b"],
        [
            [
                Segment(0, 0, 0, 0, None),
                Segment(5, 0, 1, 0, None),
                Segment(10, 1, 0, 0, None),
            ],
            [Segment(1, 1, 0, 1, None)],
        ],
    )


def test_merge_keeps_duplicate_lists_and_stable_equal_column_order() -> None:
    first = SourceMap(
        "first.js",
        ["same"],
        ["n"],
        ["first"],
        [[Segment(0, 0, 2, 3, 0), Segment(0, None, None, None, None)]],
    )
    second = SourceMap(
        None,
        ["same"],
        ["n"],
        [None],
        [[Segment(1, 0, 6, 7, None), Segment(2, 0, 4, 5, 0)]],
    )

    assert merge(
        None,
        [(0, 2, first), (0, 0, second)],
    ) == SourceMap(
        None,
        ["same", "same"],
        ["n", "n"],
        ["first", None],
        [
            [
                Segment(1, 1, 6, 7, None),
                Segment(2, 0, 2, 3, 0),
                Segment(2, None, None, None, None),
                Segment(2, 1, 4, 5, 1),
            ]
        ],
    )


def test_merge_preserves_gaps_and_trailing_empty_lines() -> None:
    section = SourceMap(None, [], [], [], [[], []])

    assert merge("gap.js", [(2, 7, section)]) == SourceMap("gap.js", [], [], [], [[], [], [], []])


def test_merge_does_not_mutate_or_alias_input_lists() -> None:
    first = SourceMap(
        "first.js",
        ["a.ts"],
        ["alpha"],
        ["source"],
        [[Segment(0, 0, 0, 0, 0), Segment(2, None, None, None, None)]],
    )
    second = SourceMap(
        "second.js",
        ["b.ts"],
        ["beta"],
        [None],
        [[Segment(1, 0, 1, 1, 0)]],
    )

    merged = merge("bundle.js", [(0, 0, first), (0, 0, second)])

    assert first == SourceMap(
        "first.js",
        ["a.ts"],
        ["alpha"],
        ["source"],
        [[Segment(0, 0, 0, 0, 0), Segment(2, None, None, None, None)]],
    )
    assert second == SourceMap(
        "second.js",
        ["b.ts"],
        ["beta"],
        [None],
        [[Segment(1, 0, 1, 1, 0)]],
    )
    assert merged.sources is not first.sources
    assert merged.names is not first.names
    assert merged.contents is not first.contents
    assert merged.lines is not first.lines
    assert merged.lines[0] is not first.lines[0]
    assert merged.lines[0] is not second.lines[0]

    merged.sources.append("new.ts")
    merged.names.append("new-name")
    merged.contents.append("new content")
    merged.lines[0].append(Segment(3, None, None, None, None))
    merged.lines.append([])

    assert first.sources == ["a.ts"]
    assert first.names == ["alpha"]
    assert first.contents == ["source"]
    assert first.lines == [[Segment(0, 0, 0, 0, 0), Segment(2, None, None, None, None)]]
    assert second.sources == ["b.ts"]
    assert second.names == ["beta"]
    assert second.contents == [None]
    assert second.lines == [[Segment(1, 0, 1, 1, 0)]]
