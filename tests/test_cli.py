import importlib
import inspect
import sys

import pytest

from srcwhere.base.inputs import IO
from srcwhere.cli import (
    cli,
    cmd_check,
    cmd_decode,
    cmd_lookup,
    cmd_reverse,
    cmd_stats,
    cmd_symbolize,
    cmd_vlq_decode,
    cmd_vlq_encode,
)

APP_MAP = (
    b'{"version":3,"file":"app.min.js","sources":["src/util.ts","src/main.ts"],'
    b'"names":["clamp","start"],"sourcesContent":["export function clamp(n: number): number {\\n'
    b'  return n < 0 ? 0 : n;\\n}\\n",'
    b'"import { clamp } from \\"./util\\";\\n\\nexport function start(): number {\\n'
    b'  return clamp(-5);\\n}\\n"],'
    b'"mappings":"AAAgBA,cACd,OAAO;ACCOC,cACd,OAAOD;A,GAAP"}'
)
SIMPLE_MAP = b'{"version":3,"file":"app.js","sources":["a.ts"],"mappings":"AAAA"}'
UNMAPPED_MAP = b'{"version":3,"file":"app.js","sources":["a.ts"],"mappings":"A"}'


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
        if path not in self.files:
            raise OSError(path)
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


def test_run_signature_ordered_dictionary_and_imports_are_inert(monkeypatch, capsys) -> None:
    signature = inspect.signature(cli.run)
    assert tuple(signature.parameters) == ("argv", "io")
    assert signature.parameters["argv"].annotation == list[str]
    assert signature.parameters["io"].annotation is IO
    assert signature.return_annotation is int
    assert list(cli.COMMANDS.items()) == [
        ("check", cmd_check),
        ("decode", cmd_decode),
        ("lookup", cmd_lookup),
        ("reverse", cmd_reverse),
        ("symbolize", cmd_symbolize),
        ("stats", cmd_stats),
        ("vlq-encode", cmd_vlq_encode),
        ("vlq-decode", cmd_vlq_decode),
    ]

    def unexpected_call(*args, **kwargs):
        raise AssertionError("module import executed the entry point")

    monkeypatch.setattr(cli, "run", unexpected_call)
    monkeypatch.setattr(sys, "exit", unexpected_call)
    entry_module = importlib.import_module("srcwhere.__main__")
    importlib.reload(entry_module)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_singleton_help_is_exact_and_does_not_read_inputs() -> None:
    io_stub = MemoryIO()

    assert cli.run(["--help"], io_stub) == 0
    assert io_stub.outputs == [
        (
            "usage: srcwhere check MAP\n"
            "       srcwhere decode MAP [--line N]\n"
            "       srcwhere lookup MAP LINE:COL\n"
            "       srcwhere reverse MAP SOURCE LINE:COL\n"
            "       srcwhere symbolize MAP TRACE [--file NAME]\n"
            "       srcwhere stats MAP\n"
            "       srcwhere vlq-encode NUMBER...\n"
            "       srcwhere vlq-decode TEXT\n"
        )
    ]
    assert io_stub.errors == []
    assert io_stub.events == [("out", io_stub.outputs[0])]


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            [],
            "missing command (check, decode, lookup, reverse, symbolize, stats, vlq-encode or vlq-decode)",
        ),
        (["fold", "x"], 'unknown command "fold"'),
        (["--help", "x"], 'unknown command "--help"'),
    ],
)
def test_missing_and_unknown_commands_are_reported_exactly(argv: list[str], expected: str) -> None:
    io_stub = MemoryIO()

    assert cli.run(argv, io_stub) == 2
    assert io_stub.outputs == []
    assert io_stub.errors == [f"srcwhere: {expected}\n"]
    assert io_stub.events == [("err", f"srcwhere: {expected}\n")]


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["check", "--x", "app.js.map"], 'unknown option "--x"'),
        (["decode", "app.js.map", "--line"], "--line needs a value"),
        (
            ["decode", "app.js.map", "--line", "0"],
            'invalid --line "0" (expected an integer from 1 to 1000000)',
        ),
    ],
)
def test_worked_option_errors_are_exact_and_read_no_files(argv: list[str], expected: str) -> None:
    io_stub = MemoryIO()

    assert cli.run(argv, io_stub) == 2
    assert io_stub.outputs == []
    assert io_stub.errors == [f"srcwhere: {expected}\n"]
    assert io_stub.events == [("err", f"srcwhere: {expected}\n")]


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["check"], "missing MAP"),
        (["lookup", "app.js.map"], "missing POSITION"),
        (["check", "a", "b"], "too many arguments"),
        (["symbolize", "-", "-"], "only one argument can be -"),
    ],
)
def test_worked_arity_errors_are_exact_and_read_no_files(argv: list[str], expected: str) -> None:
    io_stub = MemoryIO()

    assert cli.run(argv, io_stub) == 2
    assert io_stub.outputs == []
    assert io_stub.errors == [f"srcwhere: {expected}\n"]
    assert io_stub.events == [("err", f"srcwhere: {expected}\n")]


@pytest.mark.parametrize(
    ("argv", "files", "expected"),
    [
        (["check", "nowhere.map"], {}, '"nowhere.map": cannot read the file'),
        (["check", "bad.json"], {"bad.json": b"{"}, '"bad.json": not valid JSON'),
        (
            ["check", "list.json"],
            {"list.json": b"[]"},
            '"list.json": the top level is not an object',
        ),
        (
            ["decode", "bang.map"],
            {"bang.map": b'{"version":3,"sources":["a.ts"],"mappings":"AAA!"}'},
            '"bang.map": SM101 invalid character "!" at character 4',
        ),
        (
            ["lookup", "app.js.map", "3"],
            {"app.js.map": SIMPLE_MAP},
            'invalid position "3" (expected LINE:COLUMN, such as 12:5)',
        ),
        (
            ["reverse", "app.js.map", "src/x.ts", "1:1"],
            {"app.js.map": SIMPLE_MAP},
            'no source named "src/x.ts"',
        ),
        (
            ["vlq-encode", "9x"],
            {},
            'invalid number "9x" (expected an integer from -2147483647 to 2147483647)',
        ),
        (["vlq-decode", "AA!"], {}, 'invalid character "!" at character 3'),
        (["vlq-decode", "AAg"], {}, "incomplete number at character 3"),
        (["vlq-decode", "gggggggB"], {}, "number is too large at character 1"),
    ],
)
def test_worked_input_and_adapter_errors_are_exact(
    argv: list[str], files: dict[str, bytes | OSError], expected: str
) -> None:
    io_stub = MemoryIO(files=files)

    assert cli.run(argv, io_stub) == 2
    assert io_stub.outputs == []
    assert io_stub.errors == [f"srcwhere: {expected}\n"]
    assert io_stub.events[-1] == ("err", f"srcwhere: {expected}\n")


@pytest.mark.parametrize(
    ("argv", "files", "expected", "reads"),
    [
        (
            ["decode", "--line", "0"],
            {},
            'invalid --line "0" (expected an integer from 1 to 1000000)',
            [],
        ),
        (["decode", "--line", "0", "--x"], {}, 'unknown option "--x"', []),
        (["check", "nowhere.map", "extra"], {}, "too many arguments", []),
        (
            ["lookup", "bad.json", "3"],
            {"bad.json": b"{"},
            '"bad.json": not valid JSON',
            [("read_file", "bad.json")],
        ),
        (
            ["reverse", "app.js.map", "src/x.ts", "3"],
            {"app.js.map": SIMPLE_MAP},
            'no source named "src/x.ts"',
            [("read_file", "app.js.map")],
        ),
        (["check", "--help"], {}, 'unknown option "--help"', []),
        (
            ["decode", "--line", "--x"],
            {},
            'invalid --line "--x" (expected an integer from 1 to 1000000)',
            [],
        ),
    ],
)
def test_option_arity_and_argument_validation_precedence(
    argv: list[str],
    files: dict[str, bytes | OSError],
    expected: str,
    reads: list[tuple[str, str]],
) -> None:
    io_stub = MemoryIO(files=files)

    assert cli.run(argv, io_stub) == 2
    assert io_stub.outputs == []
    assert io_stub.errors == [f"srcwhere: {expected}\n"]
    assert io_stub.events == [*reads, ("err", f"srcwhere: {expected}\n")]


@pytest.mark.parametrize(
    ("argv", "files", "expected", "status", "reads"),
    [
        (
            ["check", "app.js.map"],
            {"app.js.map": APP_MAP},
            "ok, 8 segments\n",
            0,
            [("read_file", "app.js.map")],
        ),
        (
            ["decode", "app.js.map", "--line", "2"],
            {"app.js.map": APP_MAP},
            (
                "line  col  source         oline  ocol  name\n"
                '2     1    "src/main.ts"  3      17    "start"\n'
                '2     15   "src/main.ts"  4      3     -\n'
                '2     22   "src/main.ts"  4      10    "clamp"\n'
                "segments    3\n"
            ),
            0,
            [("read_file", "app.js.map")],
        ),
        (
            ["lookup", "app.js.map", "2:30"],
            {"app.js.map": APP_MAP},
            (
                "generated   2:30\n"
                "segment     2:22\n"
                'source      "src/main.ts"\n'
                "original    4:10\n"
                'name        "clamp"\n'
                'text        "  return clamp(-5);"\n'
            ),
            0,
            [("read_file", "app.js.map")],
        ),
        (
            ["reverse", "app.js.map", "src/main.ts", "4:5"],
            {"app.js.map": APP_MAP},
            "original    4:5\nsegment     4:3\nmatches     2\ngenerated   2:15\ngenerated   3:4\n",
            0,
            [("read_file", "app.js.map")],
        ),
        (
            ["symbolize", "app.js.map", "trace.txt"],
            {
                "app.js.map": APP_MAP,
                "trace.txt": b"Error: boom\n"
                b"    at a (https://example.com/static/app.min.js:1:16)\n"
                b"    at s (https://example.com/static/app.min.js:2:23)\n"
                b"    at https://example.com/static/app.min.js:3:1\n"
                b"    at Object.run (https://example.com/static/vendor.js:10:5)\n"
                b"start@https://example.com/static/app.min.js:2:15",
            },
            (
                "Error: boom\n"
                "    at a (src/util.ts:2:3)\n"
                "    at clamp (src/main.ts:4:10)\n"
                "    at https://example.com/static/app.min.js:3:1\n"
                "    at Object.run (https://example.com/static/vendor.js:10:5)\n"
                "start@src/main.ts:4:3"
            ),
            1,
            [("read_file", "app.js.map"), ("read_file", "trace.txt")],
        ),
        (
            ["stats", "app.js.map"],
            {"app.js.map": APP_MAP},
            (
                "lines       3\n"
                "segments    8\n"
                "mapped      7\n"
                "sources     2\n"
                "used        2\n"
                "names       2\n"
                "named       3\n"
                "content     2\n"
                'source      "src/util.ts" 3\n'
                'source      "src/main.ts" 4\n'
            ),
            0,
            [("read_file", "app.js.map")],
        ),
        (["vlq-encode", "0", "1", "-1", "16"], {}, "ACDgB\n", 0, []),
        (["vlq-decode", "ACDgB"], {}, "0 1 -1 16\n", 0, []),
    ],
)
def test_all_successful_command_routes_return_one_complete_output(
    argv: list[str],
    files: dict[str, bytes | OSError],
    expected: str,
    status: int,
    reads: list[tuple[str, str]],
) -> None:
    io_stub = MemoryIO(files=files)

    assert cli.run(argv, io_stub) == status
    assert io_stub.outputs == [expected]
    assert io_stub.errors == []
    assert io_stub.events == [*reads, ("out", expected)]


def test_repeated_line_options_use_the_last_value_across_ordinary_arguments() -> None:
    expected = (
        "line  col  source         oline  ocol  name\n"
        '2     1    "src/main.ts"  3      17    "start"\n'
        '2     15   "src/main.ts"  4      3     -\n'
        '2     22   "src/main.ts"  4      10    "clamp"\n'
        "segments    3\n"
    )
    io_stub = MemoryIO(files={"app.js.map": APP_MAP})

    assert cli.run(["decode", "--line", "0", "app.js.map", "--line", "2"], io_stub) == 0
    assert io_stub.outputs == [expected]
    assert io_stub.errors == []
    assert io_stub.events == [("read_file", "app.js.map"), ("out", expected)]


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["vlq-encode"], "missing NUMBER"),
        (["reverse", "app.js.map"], "missing SOURCE"),
        (["lookup", "app.js.map"], "missing POSITION"),
        (["symbolize", "app.js.map"], "missing TRACE"),
        (["vlq-decode"], "missing TEXT"),
    ],
)
def test_first_absent_command_argument_is_named_without_reading_files(
    argv: list[str], expected: str
) -> None:
    io_stub = MemoryIO()

    assert cli.run(argv, io_stub) == 2
    assert io_stub.outputs == []
    assert io_stub.errors == [f"srcwhere: {expected}\n"]
    assert io_stub.events == [("err", f"srcwhere: {expected}\n")]


def test_vlq_encode_accepts_twenty_numbers_and_rejects_twenty_one() -> None:
    twenty = [
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
    ]
    success_io = MemoryIO()

    assert cli.run(["vlq-encode", *twenty], success_io) == 0
    assert success_io.outputs == ["AAAAAAAAAAAAAAAAAAAA\n"]
    assert success_io.errors == []
    assert success_io.events == [("out", "AAAAAAAAAAAAAAAAAAAA\n")]

    failure_io = MemoryIO()
    assert (
        cli.run(
            [
                "vlq-encode",
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
                "0",
            ],
            failure_io,
        )
        == 2
    )
    assert failure_io.outputs == []
    assert failure_io.errors == ["srcwhere: too many arguments\n"]
    assert failure_io.events == [("err", "srcwhere: too many arguments\n")]


@pytest.mark.parametrize(
    ("argv", "files", "expected", "status"),
    [
        (
            ["check", "bad.map"],
            {"bad.map": b'{"version":2,"sources":["a.ts"],"mappings":"AAAA"}'},
            "SM001 version must be 3\n1 problem\n",
            1,
        ),
        (
            ["lookup", "map.json", "1:1"],
            {"map.json": UNMAPPED_MAP},
            "generated   1:1\nresult      unmapped\n",
            1,
        ),
        (
            ["reverse", "map.json", "a.ts", "2:1"],
            {"map.json": SIMPLE_MAP},
            "original    2:1\nresult      unmapped\n",
            1,
        ),
        (
            ["symbolize", "map.json", "trace.txt"],
            {"map.json": UNMAPPED_MAP, "trace.txt": b"at app.js:1:1"},
            "at app.js:1:1",
            1,
        ),
    ],
)
def test_negative_command_answers_keep_status_and_single_stdout_call(
    argv: list[str], files: dict[str, bytes | OSError], expected: str, status: int
) -> None:
    io_stub = MemoryIO(files=files)

    assert cli.run(argv, io_stub) == status
    assert io_stub.outputs == [expected]
    assert io_stub.errors == []
    assert io_stub.events[-1] == ("out", expected)


@pytest.mark.parametrize(
    ("trace", "expected"),
    [(b"", ""), (b"at app.js:1:1", "at a.ts:1:1")],
)
def test_successful_symbolize_preserves_empty_and_non_lf_output(
    trace: bytes, expected: str
) -> None:
    io_stub = MemoryIO(files={"map.json": SIMPLE_MAP, "trace.txt": trace})

    assert cli.run(["symbolize", "map.json", "trace.txt"], io_stub) == 0
    assert io_stub.outputs == [expected]
    assert io_stub.errors == []
    assert io_stub.events == [
        ("read_file", "map.json"),
        ("read_file", "trace.txt"),
        ("out", expected),
    ]


def test_dispatch_reports_malformed_stdin_and_json_without_tracebacks() -> None:
    stdin_io = MemoryIO(stdin=b"AB\xff\n")

    assert cli.run(["check", "-"], stdin_io) == 2
    assert stdin_io.outputs == []
    assert stdin_io.errors == ["srcwhere: <stdin>: input is not valid UTF-8\n"]
    assert stdin_io.events == [
        ("read_stdin", "-"),
        ("err", "srcwhere: <stdin>: input is not valid UTF-8\n"),
    ]

    malformed_io = MemoryIO(files={"bad.json": b"{"})
    assert cli.run(["check", "bad.json"], malformed_io) == 2
    assert malformed_io.outputs == []
    assert malformed_io.errors == ['srcwhere: "bad.json": not valid JSON\n']
    assert malformed_io.events == [
        ("read_file", "bad.json"),
        ("err", 'srcwhere: "bad.json": not valid JSON\n'),
    ]

    deep_json = (
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
        b"]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]"
    )
    deep_io = MemoryIO(files={"deep.json": deep_json})

    assert cli.run(["check", "deep.json"], deep_io) == 2
    assert deep_io.outputs == []
    assert deep_io.errors == ['srcwhere: "deep.json": not valid JSON\n']
    assert deep_io.events == [
        ("read_file", "deep.json"),
        ("err", 'srcwhere: "deep.json": not valid JSON\n'),
    ]
