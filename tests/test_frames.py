"""Contract tests for the supported stack-frame forms."""

import dataclasses
import json
from dataclasses import asdict, fields
from inspect import signature

import pytest

from srcwhere.trace.frames import Frame, parse_frame, render_frame


def test_frame_api_fields_and_signatures():
    assert [field.name for field in fields(Frame)] == [
        "kind",
        "indent",
        "func",
        "file",
        "line",
        "col",
    ]
    assert [field.type for field in fields(Frame)] == [
        str,
        str,
        str | None,
        str,
        int,
        int,
    ]
    parse_signature = signature(parse_frame)
    assert list(parse_signature.parameters) == ["text"]
    assert parse_signature.parameters["text"].annotation is str
    assert parse_signature.return_annotation == Frame | None
    render_signature = signature(render_frame)
    assert list(render_signature.parameters) == ["frame"]
    assert render_signature.parameters["frame"].annotation is Frame
    assert render_signature.return_annotation is str

    frame = Frame("v8", "  ", "f", "app.js", 12, 5)
    assert (
        frame.kind,
        frame.indent,
        frame.func,
        frame.file,
        frame.line,
        frame.col,
    ) == ("v8", "  ", "f", "app.js", 12, 5)


def test_frame_is_frozen():
    frame = Frame("v8", "  ", "f", "app.js", 12, 5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        frame.line = 13


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            " \tat f (app.js:12:5)",
            Frame("v8", " \t", "f", "app.js", 12, 5),
        ),
    ],
)
def test_parses_named_v8_frames(text, expected):
    assert parse_frame(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "\tat https://example.com/app.js:1:16",
            Frame("v8bare", "\t", None, "https://example.com/app.js", 1, 16),
        ),
    ],
)
def test_parses_bare_v8_frames(text, expected):
    frame = parse_frame(text)
    assert frame == expected
    assert json.dumps(asdict(frame), separators=(",", ":")) == (
        '{"kind":"v8bare","indent":"\\t","func":null,'
        '"file":"https://example.com/app.js","line":1,"col":16}'
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("start@app.js:2:15", Frame("gecko", "", "start", "app.js", 2, 15)),
        ("@app.js:1:1", Frame("gecko", "", "", "app.js", 1, 1)),
        (" \tf@app.js:1:2", Frame("gecko", "", " \tf", "app.js", 1, 2)),
    ],
)
def test_parses_gecko_and_preserves_function_text(text, expected):
    assert parse_frame(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("at f@x (app.js:1:2)", Frame("v8", "", "f@x", "app.js", 1, 2)),
        ("at f@app.js:1:2", Frame("v8bare", "", None, "f@app.js", 1, 2)),
    ],
)
def test_frame_syntax_uses_v8_then_bare_priority(text, expected):
    assert parse_frame(text) == expected


def test_v8_function_selection_is_greedy():
    assert parse_frame("at f (old.js:1:2) (new.js:3:4)") == Frame(
        "v8",
        "",
        "f (old.js:1:2)",
        "new.js",
        3,
        4,
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("f@a@b:9999999:9999999", Frame("gecko", "", "f", "a@b", 9999999, 9999999)),
        (
            "at C:\\src\\é.js:1:2",
            Frame("v8bare", "", None, "C:\\src\\é.js", 1, 2),
        ),
    ],
)
def test_accepts_filename_and_position_boundaries(text, expected):
    assert parse_frame(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "at :1:2",
        "at a b:1:2",
        "at a\tb:1:2",
        "at a(b:1:2",
        "at a)b:1:2",
    ],
)
def test_rejects_empty_or_excluded_filename_characters(text):
    assert parse_frame(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "at a.js:0:1",
        "at a.js:1:0",
        "at a.js:01:2",
        "at a.js:1:02",
        "at a.js:+1:2",
        "at a.js:1:-2",
        "at a.js:١:2",
        "at a.js:1:２",
        "at a.js:10000000:2",
        "at a.js:1:10000000",
    ],
)
def test_rejects_invalid_position_digits_and_bounds(text):
    assert parse_frame(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Error: boom",
        "at a.js:1",
        "at  (a.js:1:2)",
        "at f (a.js:1:2",
        "at f (a.js:1:2) ",
        "at a.js:1:2\n",
        "f@a.js:1:2\r",
        "at\ta.js:1:2",
        "at f (a.js:1:2)junk",
    ],
)
def test_rejects_malformed_non_frames_and_trailing_syntax(text):
    assert parse_frame(text) is None


@pytest.mark.parametrize(
    ("frame", "expected"),
    [
        (
            Frame("v8", " \t", "Object.run", "src/main.ts", 4, 10),
            " \tat Object.run (src/main.ts:4:10)",
        ),
        (
            Frame("v8bare", "  ", None, "src/util.ts", 2, 3),
            "  at src/util.ts:2:3",
        ),
        (
            Frame("gecko", "", "start", "src/main.ts", 4, 3),
            "start@src/main.ts:4:3",
        ),
        (Frame("gecko", "", "", "a.ts", 1, 1), "@a.ts:1:1"),
        (Frame("gecko", "", " \tf", "a.ts", 1, 2), " \tf@a.ts:1:2"),
    ],
)
def test_renders_valid_frames_exactly(frame, expected):
    assert render_frame(frame) == expected
