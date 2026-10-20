from collections.abc import Callable
from inspect import signature
from typing import get_type_hints

import pytest

from srcwhere.base.fail import Fail
from srcwhere.base.inputs import IO
from srcwhere.cli.cmd_lookup import ARGS as LOOKUP_ARGS
from srcwhere.cli.cmd_lookup import MAX as LOOKUP_MAX
from srcwhere.cli.cmd_lookup import SPECS as LOOKUP_SPECS
from srcwhere.cli.cmd_lookup import USAGE as LOOKUP_USAGE
from srcwhere.cli.cmd_lookup import run_lookup
from srcwhere.cli.cmd_reverse import ARGS as REVERSE_ARGS
from srcwhere.cli.cmd_reverse import MAX as REVERSE_MAX
from srcwhere.cli.cmd_reverse import SPECS as REVERSE_SPECS
from srcwhere.cli.cmd_reverse import USAGE as REVERSE_USAGE
from srcwhere.cli.cmd_reverse import run_reverse

Runner = Callable[[list[str], dict, IO], tuple[str, int]]


class MemoryIO:
    def __init__(
        self,
        files: dict[str, bytes | OSError] | None = None,
        stdin: bytes | OSError = b"",
    ) -> None:
        self.files = files or {}
        self.stdin = stdin
        self.stdin_reads = 0
        self.file_reads: list[str] = []
        self.outputs: list[str] = []
        self.errors: list[str] = []

    def read_stdin(self) -> bytes:
        self.stdin_reads += 1
        if isinstance(self.stdin, OSError):
            raise self.stdin
        return self.stdin

    def read_file(self, path: str) -> bytes:
        self.file_reads.append(path)
        if path not in self.files:
            raise OSError("not found")
        value = self.files[path]
        if isinstance(value, OSError):
            raise value
        return value

    def out(self, text: str) -> None:
        self.outputs.append(text)

    def err(self, text: str) -> None:
        self.errors.append(text)


APP_MAP = (
    b'{"version":3,"file":"app.min.js","sources":["src/util.ts","src/main.ts"],'
    b'"names":["clamp","start"],"sourcesContent":'
    b'["export function clamp(n: number): number {\\n  return n < 0 ? 0 : n;\\n}\\n",'
    b'"import { clamp } from \\"./util\\";\\n\\nexport function start(): number {\\n  return clamp(-5);\\n}\\n"],'
    b'"mappings":"AAAgBA,cACd,OAAO;ACCOC,cACd,OAAOD;A,GAAP"}'
)


def test_metadata_and_public_signatures_match_the_command_contract() -> None:
    assert LOOKUP_USAGE == "       srcwhere lookup MAP LINE:COL"
    assert LOOKUP_ARGS == ["MAP", "POSITION"]
    assert LOOKUP_MAX == 2
    assert LOOKUP_SPECS == []
    assert REVERSE_USAGE == "       srcwhere reverse MAP SOURCE LINE:COL"
    assert REVERSE_ARGS == ["MAP", "SOURCE", "POSITION"]
    assert REVERSE_MAX == 3
    assert REVERSE_SPECS == []

    assert list(signature(run_lookup).parameters) == ["args", "options", "io"]
    assert get_type_hints(run_lookup) == {
        "args": list[str],
        "options": dict,
        "io": IO,
        "return": tuple[str, int],
    }
    assert list(signature(run_reverse).parameters) == ["args", "options", "io"]
    assert get_type_hints(run_reverse) == {
        "args": list[str],
        "options": dict,
        "io": IO,
        "return": tuple[str, int],
    }


def test_lookup_returns_the_complete_request_example_without_writing_io() -> None:
    io_stub = MemoryIO(files={"app.js.map": APP_MAP})

    result = run_lookup(["app.js.map", "2:30"], {}, io_stub)

    assert result == (
        (
            "generated   2:30\n"
            "segment     2:22\n"
            'source      "src/main.ts"\n'
            "original    4:10\n"
            'name        "clamp"\n'
            'text        "  return clamp(-5);"\n'
        ),
        0,
    )
    assert io_stub.file_reads == ["app.js.map"]
    assert io_stub.stdin_reads == 0
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_lookup_keeps_equal_column_winner_and_optional_empty_values() -> None:
    io_stub = MemoryIO(
        files={
            "values.map": (
                b'{"version":3,"sources":["first.ts",""],"names":[""],'
                b'"sourcesContent":["first text",""],"mappings":"AAAAA;ACAAA"}'
            ),
            "same-column.map": (
                b'{"version":3,"sources":["first.ts","second.ts"],"mappings":"AAAA,ACAA"}'
            ),
            "missing.map": b'{"version":3,"sources":["a.ts"],"mappings":"AAAA"}',
            "contents.map": (
                b'{"version":3,"sources":["a.ts"],"sourcesContent":["first\\r\\nsecond\\r\\n"],'
                b'"mappings":"AAAA;AACA;AACA"}'
            ),
            "short.map": (
                b'{"version":3,"sources":["a.ts"],"sourcesContent":["only"],"mappings":"AAAA;AACA"}'
            ),
        }
    )

    first = run_lookup(["values.map", "1:1"], {}, io_stub)
    empty_values = run_lookup(["values.map", "2:1"], {}, io_stub)
    equal_column_winner = run_lookup(["same-column.map", "1:1"], {}, io_stub)
    absent_optional_values = run_lookup(["missing.map", "1:1"], {}, io_stub)
    crlf_first_line = run_lookup(["contents.map", "1:1"], {}, io_stub)
    crlf_second_line = run_lookup(["contents.map", "2:1"], {}, io_stub)
    terminal_empty_line = run_lookup(["contents.map", "3:1"], {}, io_stub)
    absent_content_line = run_lookup(["short.map", "2:1"], {}, io_stub)

    assert first == (
        (
            "generated   1:1\n"
            "segment     1:1\n"
            'source      "first.ts"\n'
            "original    1:1\n"
            'name        ""\n'
            'text        "first text"\n'
        ),
        0,
    )
    assert empty_values == (
        (
            "generated   2:1\n"
            "segment     2:1\n"
            'source      ""\n'
            "original    1:1\n"
            'name        ""\n'
            'text        ""\n'
        ),
        0,
    )
    assert equal_column_winner == (
        'generated   1:1\nsegment     1:1\nsource      "second.ts"\noriginal    1:1\n',
        0,
    )
    assert absent_optional_values == (
        'generated   1:1\nsegment     1:1\nsource      "a.ts"\noriginal    1:1\n',
        0,
    )
    assert crlf_first_line == (
        (
            "generated   1:1\n"
            "segment     1:1\n"
            'source      "a.ts"\n'
            "original    1:1\n"
            'text        "first"\n'
        ),
        0,
    )
    assert crlf_second_line == (
        (
            "generated   2:1\n"
            "segment     2:1\n"
            'source      "a.ts"\n'
            "original    2:1\n"
            'text        "second"\n'
        ),
        0,
    )
    assert terminal_empty_line == (
        'generated   3:1\nsegment     3:1\nsource      "a.ts"\noriginal    3:1\ntext        ""\n',
        0,
    )
    assert absent_content_line == (
        'generated   2:1\nsegment     2:1\nsource      "a.ts"\noriginal    2:1\n',
        0,
    )
    assert io_stub.file_reads == [
        "values.map",
        "values.map",
        "same-column.map",
        "missing.map",
        "contents.map",
        "contents.map",
        "contents.map",
        "short.map",
    ]
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_lookup_sanitizes_source_name_and_source_text() -> None:
    io_stub = MemoryIO(
        files={
            "safe.map": (
                b'{"version":3,"sources":["src/\xc3\xa9.ts"],'
                b'"names":["cl\\u0001amp"],"sourcesContent":["line\\t\xc3\xa9"],'
                b'"mappings":"AAAAA"}'
            )
        }
    )

    result = run_lookup(["safe.map", "1:1"], {}, io_stub)

    assert result == (
        (
            "generated   1:1\n"
            "segment     1:1\n"
            'source      "src/?.ts"\n'
            "original    1:1\n"
            'name        "cl?amp"\n'
            'text        "line??"\n'
        ),
        0,
    )
    assert io_stub.file_reads == ["safe.map"]
    assert io_stub.outputs == []
    assert io_stub.errors == []


@pytest.mark.parametrize(
    ("map_name", "map_bytes", "position", "expected", "code"),
    [
        (
            "app.js.map",
            APP_MAP,
            "3:2",
            "generated   3:2\nresult      unmapped\n",
            1,
        ),
        (
            "app.js.map",
            APP_MAP,
            "9:1",
            "generated   9:1\nresult      unmapped\n",
            1,
        ),
        (
            "edges.map",
            b'{"version":3,"sources":["a.ts"],"mappings":";CAAA,C,CAAA;A;"}',
            "1:1",
            "generated   1:1\nresult      unmapped\n",
            1,
        ),
        (
            "edges.map",
            b'{"version":3,"sources":["a.ts"],"mappings":";CAAA,C,CAAA;A;"}',
            "2:1",
            "generated   2:1\nresult      unmapped\n",
            1,
        ),
        (
            "edges.map",
            b'{"version":3,"sources":["a.ts"],"mappings":";CAAA,C,CAAA;A;"}',
            "2:3",
            "generated   2:3\nresult      unmapped\n",
            1,
        ),
        (
            "edges.map",
            b'{"version":3,"sources":["a.ts"],"mappings":";CAAA,C,CAAA;A;"}',
            "2:4",
            'generated   2:4\nsegment     2:4\nsource      "a.ts"\noriginal    1:1\n',
            0,
        ),
        (
            "edges.map",
            b'{"version":3,"sources":["a.ts"],"mappings":";CAAA,C,CAAA;A;"}',
            "3:2",
            "generated   3:2\nresult      unmapped\n",
            1,
        ),
    ],
)
def test_lookup_unmapped_barriers_empty_lines_and_out_of_range_positions(
    map_name: str, map_bytes: bytes, position: str, expected: str, code: int
) -> None:
    io_stub = MemoryIO(files={map_name: map_bytes})

    assert run_lookup([map_name, position], {}, io_stub) == (expected, code)
    assert io_stub.file_reads == [map_name]
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_reverse_returns_the_complete_request_example_without_writing_io() -> None:
    io_stub = MemoryIO(files={"app.js.map": APP_MAP})

    result = run_reverse(["app.js.map", "src/main.ts", "4:5"], {}, io_stub)

    assert result == (
        "original    4:5\nsegment     4:3\nmatches     2\ngenerated   2:15\ngenerated   3:4\n",
        0,
    )
    assert io_stub.file_reads == ["app.js.map"]
    assert io_stub.stdin_reads == 0
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_reverse_uses_best_column_and_preserves_duplicate_source_matches() -> None:
    duplicate_io = MemoryIO(
        files={
            "duplicates.map": (
                b'{"version":3,"sources":["a.ts","a.ts","unused.ts"],'
                b'"mappings":"AAAA,ECAE,ADAA;ACAA"}'
            )
        }
    )

    duplicate_matches = run_reverse(["duplicates.map", "a.ts", "1:4"], {}, duplicate_io)
    zero_column_io = MemoryIO(
        files={"zero.map": b'{"version":3,"sources":["a.ts"],"mappings":"AAAA"}'}
    )
    zero_column_match = run_reverse(["zero.map", "a.ts", "1:1"], {}, zero_column_io)

    assert duplicate_matches == (
        (
            "original    1:4\n"
            "segment     1:3\n"
            "matches     3\n"
            "generated   1:3\n"
            "generated   1:3\n"
            "generated   2:1\n"
        ),
        0,
    )
    assert zero_column_match == (
        "original    1:1\nsegment     1:1\nmatches     1\ngenerated   1:1\n",
        0,
    )
    assert duplicate_io.file_reads == ["duplicates.map"]
    assert zero_column_io.file_reads == ["zero.map"]
    assert duplicate_io.outputs == []
    assert duplicate_io.errors == []
    assert zero_column_io.outputs == []
    assert zero_column_io.errors == []


@pytest.mark.parametrize(
    ("source", "position"),
    [
        ("a.ts", "1:3"),
        ("a.ts", "2:9"),
        ("unused.ts", "1:9"),
    ],
)
def test_reverse_unmapped_answers_cover_before_best_missing_line_and_unused_source(
    source: str, position: str
) -> None:
    io_stub = MemoryIO(
        files={
            "negative.map": (b'{"version":3,"sources":["a.ts","unused.ts"],"mappings":"AAAG;A"}')
        }
    )

    assert run_reverse(["negative.map", source, position], {}, io_stub) == (
        f"original    {position}\nresult      unmapped\n",
        1,
    )
    assert io_stub.file_reads == ["negative.map"]
    assert io_stub.outputs == []
    assert io_stub.errors == []


@pytest.mark.parametrize(
    ("runner", "args", "files", "expected"),
    [
        (
            run_lookup,
            ["bad.json", "3"],
            {"bad.json": b"{"},
            '"bad.json": not valid JSON',
        ),
        (
            run_lookup,
            ["bang.map", "3"],
            {
                "bang.map": (
                    b'{"version":3,"sources":["a.ts","b.ts"],"names":["n"],"mappings":"AAA!"}'
                )
            },
            '"bang.map": SM101 invalid character "!" at character 4',
        ),
        (
            run_lookup,
            ["nowhere.map", "3"],
            {},
            '"nowhere.map": cannot read the file',
        ),
        (
            run_reverse,
            ["bad.json", "src/x.ts", "3"],
            {"bad.json": b"{"},
            '"bad.json": not valid JSON',
        ),
        (
            run_reverse,
            ["bang.map", "src/x.ts", "3"],
            {
                "bang.map": (
                    b'{"version":3,"sources":["a.ts","b.ts"],"names":["n"],"mappings":"AAA!"}'
                )
            },
            '"bang.map": SM101 invalid character "!" at character 4',
        ),
        (
            run_reverse,
            ["nowhere.map", "src/x.ts", "3"],
            {},
            '"nowhere.map": cannot read the file',
        ),
    ],
)
def test_map_loading_errors_precede_later_argument_validation(
    runner: Runner,
    args: list[str],
    files: dict[str, bytes | OSError],
    expected: str,
) -> None:
    io_stub = MemoryIO(files=files)

    with pytest.raises(Fail) as error:
        runner(args, {}, io_stub)

    assert str(error.value) == expected
    assert io_stub.file_reads == [args[0]]
    assert io_stub.stdin_reads == 0
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_reverse_checks_source_membership_before_position_and_sanitizes_it() -> None:
    io_stub = MemoryIO(files={"valid.map": b'{"version":3,"sources":["a.ts"],"mappings":"AAAA"}'})

    with pytest.raises(Fail) as missing_source:
        run_reverse(["valid.map", "missing\nsource", "3"], {}, io_stub)
    with pytest.raises(Fail) as invalid_position:
        run_reverse(["valid.map", "a.ts", "3"], {}, io_stub)

    assert str(missing_source.value) == 'no source named "missing?source"'
    assert (
        str(invalid_position.value) == 'invalid position "3" (expected LINE:COLUMN, such as 12:5)'
    )
    assert io_stub.file_reads == ["valid.map", "valid.map"]
    assert io_stub.outputs == []
    assert io_stub.errors == []


@pytest.mark.parametrize(
    ("runner", "args", "expected", "code"),
    [
        (
            run_lookup,
            ["map", "1:1"],
            'generated   1:1\nsegment     1:1\nsource      "a.ts"\noriginal    1:1\ntext        "x"\n',
            0,
        ),
        (
            run_lookup,
            ["map", "12:5"],
            "generated   12:5\nresult      unmapped\n",
            1,
        ),
        (
            run_lookup,
            ["map", "9999999:9999999"],
            "generated   9999999:9999999\nresult      unmapped\n",
            1,
        ),
        (
            run_reverse,
            ["map", "a.ts", "1:1"],
            "original    1:1\nsegment     1:1\nmatches     1\ngenerated   1:1\n",
            0,
        ),
        (
            run_reverse,
            ["map", "a.ts", "12:5"],
            "original    12:5\nresult      unmapped\n",
            1,
        ),
        (
            run_reverse,
            ["map", "a.ts", "9999999:9999999"],
            "original    9999999:9999999\nresult      unmapped\n",
            1,
        ),
        (
            run_lookup,
            ["map", "0:1"],
            'invalid position "0:1" (expected LINE:COLUMN, such as 12:5)',
            None,
        ),
        (
            run_lookup,
            ["map", "1"],
            'invalid position "1" (expected LINE:COLUMN, such as 12:5)',
            None,
        ),
        (
            run_lookup,
            ["map", "1:2:3"],
            'invalid position "1:2:3" (expected LINE:COLUMN, such as 12:5)',
            None,
        ),
        (
            run_lookup,
            ["map", "01:1"],
            'invalid position "01:1" (expected LINE:COLUMN, such as 12:5)',
            None,
        ),
        (
            run_lookup,
            ["map", "+1:1"],
            'invalid position "+1:1" (expected LINE:COLUMN, such as 12:5)',
            None,
        ),
        (
            run_lookup,
            ["map", "10000000:1"],
            'invalid position "10000000:1" (expected LINE:COLUMN, such as 12:5)',
            None,
        ),
        (
            run_reverse,
            ["map", "a.ts", "0:1"],
            'invalid position "0:1" (expected LINE:COLUMN, such as 12:5)',
            None,
        ),
        (
            run_reverse,
            ["map", "a.ts", "1"],
            'invalid position "1" (expected LINE:COLUMN, such as 12:5)',
            None,
        ),
        (
            run_reverse,
            ["map", "a.ts", "1:2:3"],
            'invalid position "1:2:3" (expected LINE:COLUMN, such as 12:5)',
            None,
        ),
        (
            run_reverse,
            ["map", "a.ts", "01:1"],
            'invalid position "01:1" (expected LINE:COLUMN, such as 12:5)',
            None,
        ),
        (
            run_reverse,
            ["map", "a.ts", "+1:1"],
            'invalid position "+1:1" (expected LINE:COLUMN, such as 12:5)',
            None,
        ),
        (
            run_reverse,
            ["map", "a.ts", "10000000:1"],
            'invalid position "10000000:1" (expected LINE:COLUMN, such as 12:5)',
            None,
        ),
    ],
)
def test_position_boundaries_and_syntax_follow_contract(
    runner: Runner, args: list[str], expected: str, code: int | None
) -> None:
    io_stub = MemoryIO(
        files={
            "map": (b'{"version":3,"sources":["a.ts"],"sourcesContent":["x"],"mappings":"AAAA"}')
        }
    )

    if code is None:
        with pytest.raises(Fail) as error:
            runner(args, {}, io_stub)
        assert str(error.value) == expected
    else:
        assert runner(args, {}, io_stub) == (expected, code)
    assert io_stub.file_reads == ["map"]
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_named_input_and_stdin_are_equivalent_and_adapters_do_not_write_io() -> None:
    named_lookup_io = MemoryIO(files={"shared.map": APP_MAP})
    stdin_lookup_io = MemoryIO(stdin=APP_MAP)
    named_lookup = run_lookup(["shared.map", "2:30"], {}, named_lookup_io)
    stdin_lookup = run_lookup(["-", "2:30"], {}, stdin_lookup_io)

    named_reverse_io = MemoryIO(files={"shared.map": APP_MAP})
    stdin_reverse_io = MemoryIO(stdin=APP_MAP)
    named_reverse = run_reverse(["shared.map", "src/main.ts", "4:5"], {}, named_reverse_io)
    stdin_reverse = run_reverse(["-", "src/main.ts", "4:5"], {}, stdin_reverse_io)

    assert stdin_lookup == named_lookup
    assert stdin_reverse == named_reverse
    assert named_lookup_io.file_reads == ["shared.map"]
    assert stdin_lookup_io.file_reads == []
    assert stdin_lookup_io.stdin_reads == 1
    assert named_reverse_io.file_reads == ["shared.map"]
    assert stdin_reverse_io.file_reads == []
    assert stdin_reverse_io.stdin_reads == 1
    assert named_lookup_io.stdin_reads == 0
    assert named_reverse_io.stdin_reads == 0
    assert named_lookup_io.outputs == []
    assert named_lookup_io.errors == []
    assert stdin_lookup_io.outputs == []
    assert stdin_lookup_io.errors == []
    assert named_reverse_io.outputs == []
    assert named_reverse_io.errors == []
    assert stdin_reverse_io.outputs == []
    assert stdin_reverse_io.errors == []
