import inspect

import pytest

from srcwhere.base.fail import Fail
from srcwhere.base.inputs import IO
from srcwhere.base.options import Spec
from srcwhere.cli import cmd_symbolize, cmd_vlq_decode, cmd_vlq_encode

MAP_APP = b'{"version":3,"file":"app.js","sources":["a.ts"],"mappings":"AAAA"}'
MAP_DIST = b'{"version":3,"file":"dist/app.js","sources":["a.ts"],"mappings":"AAAA"}'
MAP_NO_FILE = b'{"version":3,"sources":["a.ts"],"mappings":"AAAA"}'
MAP_EMPTY_FILE = b'{"version":3,"file":"","sources":["a.ts"],"mappings":"AAAA"}'


class MemoryIO:
    def __init__(
        self,
        files: dict[str, bytes | OSError] | None = None,
        stdin: bytes | OSError = b"",
    ) -> None:
        self.files = files or {}
        self.stdin = stdin
        self.events: list[tuple[str, str]] = []
        self.outputs: list[str] = []
        self.errors: list[str] = []

    def read_stdin(self) -> bytes:
        self.events.append(("read_stdin", "-"))
        if isinstance(self.stdin, OSError):
            raise self.stdin
        return self.stdin

    def read_file(self, path: str) -> bytes:
        self.events.append(("read_file", path))
        value = self.files[path]
        if isinstance(value, OSError):
            raise value
        return value

    def out(self, text: str) -> None:
        self.events.append(("out", text))
        self.outputs.append(text)

    def err(self, text: str) -> None:
        self.events.append(("err", text))
        self.errors.append(text)


def test_adapter_metadata_and_callable_signatures() -> None:
    assert cmd_symbolize.USAGE == "       srcwhere symbolize MAP TRACE [--file NAME]"
    assert cmd_symbolize.ARGS == ["MAP", "TRACE"]
    assert cmd_symbolize.MAX == 2
    assert cmd_symbolize.SPECS == [Spec("--file")]

    assert cmd_vlq_encode.USAGE == "       srcwhere vlq-encode NUMBER..."
    assert cmd_vlq_encode.ARGS == ["NUMBER"]
    assert cmd_vlq_encode.MAX == 20
    assert cmd_vlq_encode.SPECS == []

    assert cmd_vlq_decode.USAGE == "       srcwhere vlq-decode TEXT"
    assert cmd_vlq_decode.ARGS == ["TEXT"]
    assert cmd_vlq_decode.MAX == 1
    assert cmd_vlq_decode.SPECS == []

    for function in (
        cmd_symbolize.run_symbolize,
        cmd_vlq_encode.run_vlq_encode,
        cmd_vlq_decode.run_vlq_decode,
    ):
        signature = inspect.signature(function)
        assert tuple(signature.parameters) == ("args", "options", "io")
        assert signature.parameters["args"].annotation == list[str]
        assert signature.parameters["options"].annotation is dict
        assert signature.parameters["io"].annotation is IO
        assert signature.return_annotation == tuple[str, int]


def test_symbolize_rejects_dual_stdin_before_any_read() -> None:
    io_stub = MemoryIO()

    with pytest.raises(Fail) as error:
        cmd_symbolize.run_symbolize(["-", "-"], {}, io_stub)

    assert str(error.value) == "only one argument can be -"
    assert io_stub.events == []
    assert io_stub.outputs == []
    assert io_stub.errors == []


@pytest.mark.parametrize(
    ("map_bytes", "expected"),
    [
        (b"{", '"bad.map": not valid JSON'),
        (
            b'{"version":2,"sources":["a.ts"],"mappings":"AAAA"}',
            '"bad.map": SM001 version must be 3',
        ),
    ],
)
def test_bad_maps_fail_before_the_trace_is_read(map_bytes: bytes, expected: str) -> None:
    io_stub = MemoryIO(files={"bad.map": map_bytes, "trace.txt": b"at app.js:1:1"})

    with pytest.raises(Fail) as error:
        cmd_symbolize.run_symbolize(["bad.map", "trace.txt"], {}, io_stub)

    assert str(error.value) == expected
    assert io_stub.events == [("read_file", "bad.map")]
    assert io_stub.outputs == []
    assert io_stub.errors == []


@pytest.mark.parametrize(
    ("trace_bytes", "expected"),
    [
        (OSError("unavailable"), '"trace.txt": cannot read the file'),
        (b"AB\xff\n", '"trace.txt": input is not valid UTF-8'),
    ],
)
def test_trace_read_failures_follow_map_loading(
    trace_bytes: bytes | OSError, expected: str
) -> None:
    io_stub = MemoryIO(files={"app.map": MAP_APP, "trace.txt": trace_bytes})

    with pytest.raises(Fail) as error:
        cmd_symbolize.run_symbolize(["app.map", "trace.txt"], {}, io_stub)

    assert str(error.value) == expected
    assert io_stub.events == [("read_file", "app.map"), ("read_file", "trace.txt")]
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_either_input_can_be_stdin_and_one_leading_bom_is_removed() -> None:
    map_stdin = MemoryIO(
        files={"trace.txt": b"at app.js:1:1"},
        stdin=b'\xef\xbb\xbf{"version":3,"file":"app.js","sources":["a.ts"],"mappings":"AAAA"}',
    )

    assert cmd_symbolize.run_symbolize(["-", "trace.txt"], {}, map_stdin) == (
        "at a.ts:1:1",
        0,
    )
    assert map_stdin.events == [("read_stdin", "-"), ("read_file", "trace.txt")]
    assert map_stdin.outputs == []
    assert map_stdin.errors == []

    trace_stdin = MemoryIO(files={"app.map": MAP_APP}, stdin=b"\xef\xbb\xbfat app.js:1:1")

    assert cmd_symbolize.run_symbolize(["app.map", "-"], {}, trace_stdin) == (
        "at a.ts:1:1",
        0,
    )
    assert trace_stdin.events == [("read_file", "app.map"), ("read_stdin", "-")]
    assert trace_stdin.outputs == []
    assert trace_stdin.errors == []


def test_default_file_name_uses_the_literal_slash_basename() -> None:
    io_stub = MemoryIO(
        files={
            "app.map": MAP_DIST,
            "trace.txt": b"at https://example.com/static/app.js:1:1",
        }
    )

    assert cmd_symbolize.run_symbolize(["app.map", "trace.txt"], {}, io_stub) == (
        "at a.ts:1:1",
        0,
    )
    assert io_stub.events == [("read_file", "app.map"), ("read_file", "trace.txt")]


@pytest.mark.parametrize(
    ("map_bytes", "trace", "expected"),
    [
        (MAP_APP, "at other.js:1:1", "at a.ts:1:1"),
        (MAP_NO_FILE, "at other.js:1:1", "at a.ts:1:1"),
    ],
)
def test_explicit_file_overrides_present_or_absent_map_file(
    map_bytes: bytes, trace: str, expected: str
) -> None:
    io_stub = MemoryIO(files={"app.map": map_bytes, "trace.txt": trace.encode("utf-8")})

    assert cmd_symbolize.run_symbolize(
        ["app.map", "trace.txt"], {"--file": "other.js"}, io_stub
    ) == (expected, 0)
    assert io_stub.events == [("read_file", "app.map"), ("read_file", "trace.txt")]
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_missing_file_precedes_trace_read_and_empty_file_is_present() -> None:
    missing_file_io = MemoryIO(files={"map.json": MAP_NO_FILE, "trace.txt": OSError("unavailable")})

    with pytest.raises(Fail) as error:
        cmd_symbolize.run_symbolize(["map.json", "trace.txt"], {}, missing_file_io)

    assert str(error.value) == 'the map has no "file" (give --file NAME)'
    assert missing_file_io.events == [("read_file", "map.json")]
    assert missing_file_io.outputs == []
    assert missing_file_io.errors == []

    empty_file_io = MemoryIO(files={"map.json": MAP_EMPTY_FILE, "trace.txt": b"at app.js:1:1"})

    assert cmd_symbolize.run_symbolize(["map.json", "trace.txt"], {}, empty_file_io) == (
        "at app.js:1:1",
        0,
    )
    assert empty_file_io.events == [("read_file", "map.json"), ("read_file", "trace.txt")]
    assert empty_file_io.outputs == []
    assert empty_file_io.errors == []


def test_complete_literal_worked_example_is_remapped_exactly() -> None:
    worked_map = (
        b"""{"version":3,"file":"app.min.js","sources":["src/util.ts","src/main.ts"],"""
        b""""names":["clamp","start"],"sourcesContent":["export function clamp(n: number): number {\\n  return n < 0 ? 0 : n;\\n}\\n","""
        b""""import { clamp } from \\"./util\\";\\n\\nexport function start(): number {\\n  return clamp(-5);\\n}\\n"],"""
        b""""mappings":"AAAgBA,cACd,OAAO;ACCOC,cACd,OAAOD;A,GAAP"}"""
    )
    worked_trace = (
        b"Error: boom\n"
        b"    at a (https://example.com/static/app.min.js:1:16)\n"
        b"    at s (https://example.com/static/app.min.js:2:23)\n"
        b"    at https://example.com/static/app.min.js:3:1\n"
        b"    at Object.run (https://example.com/static/vendor.js:10:5)\n"
        b"start@https://example.com/static/app.min.js:2:15"
    )
    expected = (
        "Error: boom\n"
        "    at a (src/util.ts:2:3)\n"
        "    at clamp (src/main.ts:4:10)\n"
        "    at https://example.com/static/app.min.js:3:1\n"
        "    at Object.run (https://example.com/static/vendor.js:10:5)\n"
        "start@src/main.ts:4:3"
    )
    io_stub = MemoryIO(files={"app.js.map": worked_map, "trace.txt": worked_trace})

    assert cmd_symbolize.run_symbolize(["app.js.map", "trace.txt"], {}, io_stub) == (
        expected,
        1,
    )
    assert io_stub.events == [("read_file", "app.js.map"), ("read_file", "trace.txt")]
    assert io_stub.outputs == []
    assert io_stub.errors == []


@pytest.mark.parametrize(
    ("trace", "expected"),
    [
        ("at app.js:1:1\r\nat app.js:1:1", "at a.ts:1:1\r\nat a.ts:1:1"),
        ("at app.js:1:1\n", "at a.ts:1:1\n"),
        ("at app.js:1:1", "at a.ts:1:1"),
        ("at app.js:1:1\r", "at a.ts:1:1\r"),
        ("", ""),
    ],
)
def test_trace_line_endings_and_empty_text_are_preserved(trace: str, expected: str) -> None:
    io_stub = MemoryIO(files={"app.map": MAP_APP, "trace.txt": trace.encode("utf-8")})

    assert cmd_symbolize.run_symbolize(["app.map", "trace.txt"], {}, io_stub) == (
        expected,
        0,
    )
    assert io_stub.outputs == []
    assert io_stub.errors == []


@pytest.mark.parametrize(
    ("trace", "expected", "status"),
    [
        ("at vendor.js:1:1", "at vendor.js:1:1", 0),
        ("at app.js:1:1", "at a.ts:1:1", 0),
        ("at app.js:2:1", "at app.js:2:1", 1),
        (
            "at app.js:2:1\nat app.js:3:1",
            "at app.js:2:1\nat app.js:3:1",
            1,
        ),
    ],
)
def test_symbolize_status_tracks_only_unmapped_matching_frames(
    trace: str, expected: str, status: int
) -> None:
    io_stub = MemoryIO(
        files={
            "app.map": b'{"version":3,"file":"app.js","sources":["a.ts"],"mappings":"AAAA;A"}',
            "trace.txt": trace.encode("utf-8"),
        }
    )

    assert cmd_symbolize.run_symbolize(["app.map", "trace.txt"], {}, io_stub) == (
        expected,
        status,
    )
    assert io_stub.outputs == []
    assert io_stub.errors == []


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["0", "1", "-1", "16"], "ACDgB\n"),
        (["-123456"], "hkxH\n"),
        (["2147483647", "-2147483647"], "+/////D//////D\n"),
        (
            [
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
            ],
            "AAAAAAAAAAAAAAAAAAAA\n",
        ),
    ],
)
def test_vlq_encoder_literal_success_rows(args: list[str], expected: str) -> None:
    io_stub = MemoryIO()

    assert cmd_vlq_encode.run_vlq_encode(args, {}, io_stub) == (expected, 0)
    assert io_stub.events == []
    assert io_stub.outputs == []
    assert io_stub.errors == []


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (
            ["9x", "007"],
            'invalid number "9x" (expected an integer from -2147483647 to 2147483647)',
        ),
        (
            ["007"],
            'invalid number "007" (expected an integer from -2147483647 to 2147483647)',
        ),
        (
            ["-0"],
            'invalid number "-0" (expected an integer from -2147483647 to 2147483647)',
        ),
        (
            ["+3"],
            'invalid number "+3" (expected an integer from -2147483647 to 2147483647)',
        ),
        (
            ["2147483648"],
            'invalid number "2147483648" (expected an integer from -2147483647 to 2147483647)',
        ),
        (
            ["-2147483648"],
            'invalid number "-2147483648" (expected an integer from -2147483647 to 2147483647)',
        ),
    ],
)
def test_vlq_encoder_numeric_failures_are_exact_and_left_to_right(
    args: list[str], expected: str
) -> None:
    io_stub = MemoryIO()

    with pytest.raises(Fail) as error:
        cmd_vlq_encode.run_vlq_encode(args, {}, io_stub)

    assert str(error.value) == expected
    assert io_stub.events == []
    assert io_stub.outputs == []
    assert io_stub.errors == []


@pytest.mark.parametrize(
    ("text", "expected", "error_text"),
    [
        ("ACDgB", "0 1 -1 16\n", None),
        ("B", "0\n", None),
        ("+/////D//////D", "2147483647 -2147483647\n", None),
        ("", None, "nothing to decode"),
        ("AA!", None, 'invalid character "!" at character 3'),
        ("AAg", None, "incomplete number at character 3"),
        ("gggggggB", None, "number is too large at character 1"),
    ],
)
def test_vlq_decoder_literal_success_and_error_rows(
    text: str, expected: str | None, error_text: str | None
) -> None:
    io_stub = MemoryIO()

    if error_text is not None:
        with pytest.raises(Fail) as error:
            cmd_vlq_decode.run_vlq_decode([text], {}, io_stub)
        assert str(error.value) == error_text
    else:
        assert cmd_vlq_decode.run_vlq_decode([text], {}, io_stub) == (expected, 0)

    assert io_stub.events == []
    assert io_stub.outputs == []
    assert io_stub.errors == []
