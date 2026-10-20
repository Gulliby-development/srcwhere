import pytest

from srcwhere.smap import structure
from srcwhere.smap.model import Problem, Segment, SourceMap


def _formats(problems: list[Problem]) -> list[str]:
    return [problem.format() for problem in problems]


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        (
            {},
            [
                "SM001 version must be 3",
                "SM003 sources must be an array of strings",
                "SM006 mappings must be a string",
            ],
        ),
        (
            {
                "version": 3,
                "file": None,
                "sources": [1],
                "names": None,
                "sourcesContent": [False],
                "mappings": 1,
            },
            [
                "SM002 file must be a string",
                "SM003 sources must be an array of strings",
                "SM004 names must be an array of strings",
                "SM005 sourcesContent must be an array of strings or null",
                "SM006 mappings must be a string",
            ],
        ),
        (
            {"version": True, "sources": [], "mappings": ""},
            ["SM001 version must be 3"],
        ),
        (
            {"version": 3.0, "sources": [], "mappings": ""},
            ["SM001 version must be 3"],
        ),
        (
            {"version": 3, "sources": [], "mappings": ""},
            [],
        ),
    ],
)
def test_regular_required_fields_and_strict_version(document: dict, expected: list[str]) -> None:
    problems, source_map = structure.document_problems(document)

    assert _formats(problems) == expected
    assert (source_map is None) is bool(expected)


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        (
            {
                "version": 2,
                "file": 0,
                "sources": ["a"],
                "sourcesContent": 0,
                "mappings": "AAA!",
            },
            [
                "SM001 version must be 3",
                "SM002 file must be a string",
                "SM005 sourcesContent must be an array of strings or null",
                'SM101 invalid character "!" at character 4',
            ],
        ),
        (
            {"version": 3, "sources": None, "mappings": "!"},
            ["SM003 sources must be an array of strings"],
        ),
        (
            {"version": 3, "sources": [], "names": False, "mappings": "!"},
            ["SM004 names must be an array of strings"],
        ),
        (
            {"version": 3, "sources": ["a"], "mappings": "AAAA;AA"},
            ["SM103 segment has 2 fields (expected 1, 4 or 5) at character 6"],
        ),
    ],
)
def test_regular_error_order_and_decoder_gates(document: dict, expected: list[str]) -> None:
    problems, source_map = structure.document_problems(document)

    assert _formats(problems) == expected
    assert source_map is None


def test_decoder_gate_and_decoder_result_are_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    decoded_lines = [[Segment(2, 0, 3, 4, None)]]
    decoder_problem = Problem("SM109", "decoder result")
    calls: list[tuple[str, int, int]] = []

    def fake_decode(text: str, nsources: int, nnames: int):
        calls.append((text, nsources, nnames))
        return decoded_lines, decoder_problem if text == "problem" else None

    monkeypatch.setattr(structure, "decode_mappings", fake_decode)

    problems, source_map = structure.document_problems(
        {
            "version": 2,
            "file": 7,
            "sources": ["a"],
            "names": [],
            "sourcesContent": [False],
            "mappings": "problem",
        }
    )
    assert _formats(problems) == [
        "SM001 version must be 3",
        "SM002 file must be a string",
        "SM005 sourcesContent must be an array of strings or null",
        "SM109 decoder result",
    ]
    assert problems[-1] is decoder_problem
    assert source_map is None

    problems, source_map = structure.document_problems(
        {"version": 3, "sources": ["a"], "mappings": "valid"}
    )
    assert problems == []
    assert source_map == SourceMap(None, ["a"], [], [None], decoded_lines)

    assert structure.document_problems({"version": 3, "sources": None, "mappings": "gated"})[0] == [
        Problem("SM003", "sources must be an array of strings")
    ]
    assert structure.document_problems(
        {"version": 3, "sources": [], "names": None, "mappings": "gated"}
    )[0] == [Problem("SM004", "names must be an array of strings")]
    assert structure.document_problems({"version": 3, "sources": [], "mappings": None})[0] == [
        Problem("SM006", "mappings must be a string")
    ]
    assert calls == [("problem", 1, 0), ("valid", 1, 0)]


def test_regular_map_defaults_duplicates_ignored_keys_and_content_padding() -> None:
    problems, source_map = structure.document_problems(
        {
            "version": 3,
            "file": "x.js",
            "sources": ["a", "a", "b"],
            "names": ["n"],
            "sourcesContent": ["text"],
            "sourceRoot": "ignored/",
            "extra": True,
            "mappings": "AAAAA",
        }
    )

    assert problems == []
    assert source_map == SourceMap(
        "x.js",
        ["a", "a", "b"],
        ["n"],
        ["text", None, None],
        [[Segment(0, 0, 0, 0, 0)]],
    )

    empty_problems, empty_map = structure.document_problems(
        {"version": 3, "sources": [], "mappings": ""}
    )
    assert empty_problems == []
    assert empty_map == SourceMap(None, [], [], [], [[]])


def test_every_sources_content_entry_is_validated_before_extra_entries_are_ignored() -> None:
    problems, source_map = structure.document_problems(
        {
            "version": 3,
            "sources": ["a"],
            "sourcesContent": [None, "extra"],
            "mappings": "A",
        }
    )
    assert problems == []
    assert source_map == SourceMap(None, ["a"], [], [None], [[Segment(0, None, None, None, None)]])

    problems, source_map = structure.document_problems(
        {
            "version": 3,
            "sources": ["a"],
            "sourcesContent": [None, 0],
            "mappings": "A",
        }
    )
    assert _formats(problems) == ["SM005 sourcesContent must be an array of strings or null"]
    assert source_map is None


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        (
            {"version": 2, "file": 0, "sections": None},
            [
                "SM001 version must be 3",
                "SM002 file must be a string",
                "SM007 sections must be an array",
            ],
        ),
        (
            {"version": 3, "sections": [None, {"offset": {"line": 0}}]},
            [
                "SM008 section 1: offset must be an object with integer line and column of 0 or more",
                "SM009 section 1: map must be an object",
                "SM008 section 2: offset must be an object with integer line and column of 0 or more",
                "SM009 section 2: map must be an object",
            ],
        ),
        (
            {
                "version": 3,
                "sections": [
                    {
                        "offset": {"line": 0, "column": 0},
                        "url": "a.map",
                    }
                ],
            },
            ["SM009 section 1: map must be an object"],
        ),
    ],
)
def test_index_dispatch_and_section_problem_order(document: dict, expected: list[str]) -> None:
    problems, source_map = structure.document_problems(document)

    assert _formats(problems) == expected
    assert source_map is None


@pytest.mark.parametrize(
    "offset",
    [
        {"line": True, "column": 0},
        {"line": 0.0, "column": 0},
        {"line": 0},
        {"line": -1, "column": 0},
        {"line": 0, "column": False},
        {"line": 0, "column": -1},
        None,
    ],
)
def test_offsets_require_nonnegative_strict_integer_coordinates(offset: object) -> None:
    problems, source_map = structure.document_problems(
        {
            "version": 3,
            "sections": [
                {
                    "offset": offset,
                    "map": {"version": 3, "sources": [], "mappings": ""},
                }
            ],
        }
    )

    assert _formats(problems) == [
        "SM008 section 1: offset must be an object with integer line and column of 0 or more"
    ]
    assert source_map is None


def test_section_children_are_regular_maps_with_local_prefixed_diagnostics() -> None:
    problems, source_map = structure.document_problems(
        {
            "version": 3,
            "sections": [
                {
                    "offset": {"line": True, "column": 0},
                    "map": {
                        "version": 3,
                        "sources": ["a"],
                        "mappings": "AAA!",
                    },
                },
                {
                    "offset": {"line": -1, "column": 0},
                    "map": {},
                },
            ],
        }
    )

    assert _formats(problems) == [
        "SM008 section 1: offset must be an object with integer line and column of 0 or more",
        'SM101 section 1: invalid character "!" at character 4',
        "SM008 section 2: offset must be an object with integer line and column of 0 or more",
        "SM001 section 2: version must be 3",
        "SM003 section 2: sources must be an array of strings",
        "SM006 section 2: mappings must be a string",
    ]
    assert source_map is None


def test_index_maps_ignore_top_level_regular_fields_and_child_sections_key() -> None:
    problems, source_map = structure.document_problems(
        {
            "version": 3,
            "sections": [],
            "sources": False,
            "names": False,
            "mappings": False,
            "sourcesContent": False,
        }
    )
    assert problems == []
    assert source_map == SourceMap(None, [], [], [], [[]])

    problems, source_map = structure.document_problems(
        {
            "version": 3,
            "sections": [
                {
                    "offset": {"line": 0, "column": 0},
                    "map": {
                        "version": 3,
                        "sources": [],
                        "mappings": "",
                        "sections": False,
                    },
                }
            ],
        }
    )
    assert problems == []
    assert source_map == SourceMap(None, [], [], [], [[]])


def test_index_map_merges_section_offsets_and_adjusts_indexes() -> None:
    problems, source_map = structure.document_problems(
        {
            "version": 3,
            "file": "all.js",
            "sections": [
                {
                    "offset": {"line": 0, "column": 0},
                    "map": {
                        "version": 3,
                        "sources": ["a.ts"],
                        "mappings": "AAAA,KACA",
                    },
                },
                {
                    "offset": {"line": 0, "column": 10},
                    "map": {
                        "version": 3,
                        "sources": ["b.ts"],
                        "mappings": "AAAA;CAAC",
                    },
                },
            ],
        }
    )

    assert problems == []
    assert source_map == SourceMap(
        "all.js",
        ["a.ts", "b.ts"],
        [],
        [None, None],
        [
            [
                Segment(0, 0, 0, 0, None),
                Segment(5, 0, 1, 0, None),
                Segment(10, 1, 0, 0, None),
            ],
            [Segment(1, 1, 0, 1, None)],
        ],
    )


def test_index_map_does_not_merge_when_any_section_has_problems(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    merge_calls: list[tuple[str | None, list[tuple[int, int, SourceMap]]]] = []

    def fake_merge(file: str | None, parts: list[tuple[int, int, SourceMap]]) -> SourceMap:
        merge_calls.append((file, parts))
        return SourceMap(file, [], [], [], [[]])

    monkeypatch.setattr(structure, "merge", fake_merge)

    problems, source_map = structure.document_problems(
        {
            "version": 3,
            "file": "bundle.js",
            "sections": [
                {
                    "offset": {"line": 0, "column": 0},
                    "map": {"version": 3, "sources": [], "mappings": ""},
                },
                {
                    "offset": {"line": 0, "column": 1},
                    "map": {"version": 2, "sources": [], "mappings": ""},
                },
            ],
        }
    )

    assert _formats(problems) == ["SM001 section 2: version must be 3"]
    assert source_map is None
    assert merge_calls == []


def test_overlapping_sections_keep_order_and_concatenate_names_and_contents() -> None:
    problems, source_map = structure.document_problems(
        {
            "version": 3,
            "file": "bundle.js",
            "sections": [
                {
                    "offset": {"line": 0, "column": 0},
                    "map": {
                        "version": 3,
                        "sources": ["first.ts"],
                        "names": ["firstName"],
                        "sourcesContent": ["first content"],
                        "mappings": "AAAAA",
                    },
                },
                {
                    "offset": {"line": 0, "column": 0},
                    "map": {
                        "version": 3,
                        "sources": ["second.ts"],
                        "names": ["secondName"],
                        "sourcesContent": ["second content"],
                        "mappings": "AAAAA",
                    },
                },
            ],
        }
    )

    assert problems == []
    assert source_map == SourceMap(
        "bundle.js",
        ["first.ts", "second.ts"],
        ["firstName", "secondName"],
        ["first content", "second content"],
        [[Segment(0, 0, 0, 0, 0), Segment(0, 1, 0, 0, 1)]],
    )
