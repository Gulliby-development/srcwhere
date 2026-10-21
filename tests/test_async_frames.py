"""Regression tests for V8 async and constructor markers."""

from srcwhere.smap.model import Segment, SourceMap
from srcwhere.trace.remap import remap_trace


def _marker_map() -> SourceMap:
    return SourceMap(
        file="app.js",
        sources=["a.ts"],
        names=["load"],
        contents=[None],
        lines=[[Segment(0, 0, 2, 4, 0)]],
    )


def test_preserves_async_marker_and_indent() -> None:
    assert remap_trace(_marker_map(), "    at async go (app.js:1:1)", "app.js") == (
        "    at async load (a.ts:3:5)",
        0,
    )


def test_preserves_new_marker() -> None:
    assert remap_trace(_marker_map(), "at new Widget (app.js:1:1)", "app.js") == (
        "at new load (a.ts:3:5)",
        0,
    )


def test_preserves_async_and_new_markers_in_order() -> None:
    assert remap_trace(_marker_map(), "at async new Widget (app.js:1:1)", "app.js") == (
        "at async new load (a.ts:3:5)",
        0,
    )


def test_only_preserves_markers_followed_by_a_function_name() -> None:
    assert remap_trace(_marker_map(), "at async (app.js:1:1)", "app.js") == (
        "at load (a.ts:3:5)",
        0,
    )
    assert remap_trace(_marker_map(), "at new async x (app.js:1:1)", "app.js") == (
        "at new load (a.ts:3:5)",
        0,
    )


def test_gecko_frame_does_not_preserve_v8_markers() -> None:
    assert remap_trace(_marker_map(), "async go@app.js:1:1", "app.js") == (
        "load@a.ts:3:5",
        0,
    )
