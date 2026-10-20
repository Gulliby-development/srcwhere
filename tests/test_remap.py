"""In-memory contract tests for source-map trace remapping."""

import pytest

from srcwhere.smap.model import Segment, SourceMap
from srcwhere.trace.remap import remap_trace


def _trace_map() -> SourceMap:
    return SourceMap(
        file="ignored.js",
        sources=["a.ts"],
        names=["mapped", ""],
        contents=[None],
        lines=[
            [
                Segment(0, 0, 2, 4, 0),
                Segment(5, 0, 1, 2, None),
                Segment(9, None, None, None, None),
            ],
            [],
            [Segment(3, 0, 0, 0, 1), Segment(3, 0, 3, 1, 0)],
        ],
    )


def _empty_name_map() -> SourceMap:
    return SourceMap(
        file=None,
        sources=["a.ts"],
        names=[""],
        contents=[None],
        lines=[[Segment(0, 0, 0, 0, 0)]],
    )


def test_remaps_named_v8_frame_and_preserves_indent() -> None:
    assert remap_trace(_trace_map(), "\t at old (app.js:1:2)", "app.js") == (
        "\t at mapped (a.ts:3:5)",
        0,
    )


def test_remaps_bare_v8_frame() -> None:
    assert remap_trace(_trace_map(), "at app.js:1:1", "app.js") == ("at a.ts:3:5", 0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("old@app.js:1:1", "mapped@a.ts:3:5"),
        ("@app.js:1:1", "@a.ts:3:5"),
    ],
)
def test_remaps_named_and_empty_gecko_functions(text: str, expected: str) -> None:
    assert remap_trace(_trace_map(), text, "app.js") == (expected, 0)


def test_remaps_unnamed_segment_without_changing_function() -> None:
    assert remap_trace(_trace_map(), "at old (app.js:1:6)", "app.js") == (
        "at old (a.ts:2:3)",
        0,
    )


def test_matches_literal_slash_suffix() -> None:
    assert remap_trace(_trace_map(), "at https://example.com/static/app.js:1:1", "app.js") == (
        "at a.ts:3:5",
        0,
    )


def test_leaves_literal_nonmatching_paths_unchanged() -> None:
    text = "at myapp.js:1:1\nat APP.js:1:1\nat C:\\app.js:1:1\nat app.js?x:1:1\nat ignored.js:1:1"
    assert remap_trace(_trace_map(), text, "app.js") == (text, 0)


def test_last_equal_column_segment_wins_without_interpolation() -> None:
    assert remap_trace(_trace_map(), "at app.js:3:4", "app.js") == ("at a.ts:4:2", 0)


def test_counts_negative_lookup_results_and_unmapped_barriers() -> None:
    text = "at app.js:3:3\nat app.js:2:1\nat app.js:4:1\nat app.js:1:10"
    assert remap_trace(_trace_map(), text, "app.js") == (text, 4)


def test_counts_only_matching_parsed_frames_in_mixed_trace() -> None:
    text = "Error: boom\nat app.js:1:0\nat vendor.js:4:1\nat app.js:4:1\nat old (app.js:1:1)"
    expected = "Error: boom\nat app.js:1:0\nat vendor.js:4:1\nat app.js:4:1\nat mapped (a.ts:3:5)"
    assert remap_trace(_trace_map(), text, "app.js") == (expected, 1)


def test_empty_mapped_name_replaces_only_nonempty_functions() -> None:
    text = "at old (app.js:1:1)\nold@app.js:1:1\n@app.js:1:1\nat app.js:1:1"
    expected = "at  (a.ts:1:1)\n@a.ts:1:1\n@a.ts:1:1\nat a.ts:1:1"
    assert remap_trace(_empty_name_map(), text, "app.js") == (expected, 0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ("", 0)),
        ("\n\n", ("\n\n", 0)),
    ],
)
def test_preserves_empty_text_and_blank_lines(text: str, expected: tuple[str, int]) -> None:
    assert remap_trace(_trace_map(), text, "app.js") == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("at app.js:1:1\n", ("at a.ts:3:5\n", 0)),
        ("at app.js:1:1\r", ("at a.ts:3:5\r", 0)),
        (
            "Error\r\nat app.js:1:1\r\nat app.js:2:1\r\n\nat vendor.js:1:1",
            (
                "Error\r\nat a.ts:3:5\r\nat app.js:2:1\r\n\nat vendor.js:1:1",
                1,
            ),
        ),
    ],
)
def test_preserves_terminal_newline_and_cr_suffixes(text: str, expected: tuple[str, int]) -> None:
    assert remap_trace(_trace_map(), text, "app.js") == expected
