import inspect

import pytest

from srcwhere.base.fail import Fail
from srcwhere.base.inputs import IO
from srcwhere.base.options import Spec, parse_options
from srcwhere.cli import cmd_check, cmd_decode, cmd_stats


class MemoryIO:
    def __init__(
        self,
        files: dict[str, bytes | OSError] | None = None,
        stdin: bytes | OSError = b"",
    ) -> None:
        self.files = {} if files is None else files
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
        value = self.files[path]
        if isinstance(value, OSError):
            raise value
        return value

    def out(self, text: str) -> None:
        self.outputs.append(text)

    def err(self, text: str) -> None:
        self.errors.append(text)


def assert_no_writes(io_stub: MemoryIO) -> None:
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_command_metadata_and_run_signatures() -> None:
    assert (cmd_check.USAGE, cmd_check.ARGS, cmd_check.MAX, cmd_check.SPECS) == (
        "usage: srcwhere check MAP",
        ["MAP"],
        1,
        [],
    )
    assert (cmd_decode.USAGE, cmd_decode.ARGS, cmd_decode.MAX) == (
        "       srcwhere decode MAP [--line N]",
        ["MAP"],
        1,
    )
    assert cmd_decode.SPECS == [Spec("--line", numeric=True, lo=1, hi=1000000)]
    assert (cmd_stats.USAGE, cmd_stats.ARGS, cmd_stats.MAX, cmd_stats.SPECS) == (
        "       srcwhere stats MAP",
        ["MAP"],
        1,
        [],
    )

    for function in (cmd_check.run_check, cmd_decode.run_decode, cmd_stats.run_stats):
        signature = inspect.signature(function)
        assert list(signature.parameters) == ["args", "options", "io"]
        assert signature.parameters["args"].annotation == list[str]
        assert signature.parameters["options"].annotation == dict
        assert signature.parameters["io"].annotation == IO
        assert signature.return_annotation == tuple[str, int]


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        (b'{"version":3,"sources":[],"mappings":""}', ("ok, 0 segments\n", 0)),
        (b'{"version":3,"sources":[],"mappings":"A"}', ("ok, 1 segment\n", 0)),
        (b'{"version":3,"sources":[],"mappings":"A;A"}', ("ok, 2 segments\n", 0)),
    ],
)
def test_check_success_counts_all_segments(document: bytes, expected: tuple[str, int]) -> None:
    io_stub = MemoryIO(files={"map.json": document})

    assert cmd_check.run_check(["map.json"], {}, io_stub) == expected
    assert io_stub.file_reads == ["map.json"]
    assert io_stub.stdin_reads == 0
    assert_no_writes(io_stub)


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        (
            b'{"version":2,"sources":[],"mappings":""}',
            ("SM001 version must be 3\n1 problem\n", 1),
        ),
        (
            b'{"version":2}',
            (
                (
                    "SM001 version must be 3\n"
                    "SM003 sources must be an array of strings\n"
                    "SM006 mappings must be a string\n"
                    "3 problems\n"
                ),
                1,
            ),
        ),
        (
            b'{"version":3,"sections":[{"offset":{"line":0}}]}',
            (
                (
                    "SM008 section 1: offset must be an object with integer line and column of 0 or more\n"
                    "SM009 section 1: map must be an object\n"
                    "2 problems\n"
                ),
                1,
            ),
        ),
        (
            b'{"version":3,"sections":[{"offset":{"line":0,"column":0},"map":{"version":3,"sources":["a"],"mappings":"AAAA"}},{"offset":{"line":2,"column":0},"map":{"version":3,"sources":["b"],"mappings":"AAA!"}}]}',
            ('SM101 section 2: invalid character "!" at character 4\n1 problem\n', 1),
        ),
    ],
)
def test_check_lists_ordered_problems_and_section_prefixes(
    document: bytes, expected: tuple[str, int]
) -> None:
    io_stub = MemoryIO(files={"bad.map": document})

    assert cmd_check.run_check(["bad.map"], {}, io_stub) == expected
    assert io_stub.file_reads == ["bad.map"]
    assert io_stub.stdin_reads == 0
    assert_no_writes(io_stub)


def test_decode_renders_complete_mapping_table_literally() -> None:
    io_stub = MemoryIO(
        files={
            "map.json": (
                b'{"version":3,"sources":["a.ts"],"names":["n"],"mappings":"AAAAA,C;A;;AAAA"}'
            )
        }
    )

    assert cmd_decode.run_decode(["map.json"], {"--line": None}, io_stub) == (
        (
            "line  col  source  oline  ocol  name\n"
            '1     1    "a.ts"  1      1     "n"\n'
            "1     2    -       -      -     -\n"
            "2     1    -       -      -     -\n"
            '4     1    "a.ts"  1      1     -\n'
            "segments    4\n"
        ),
        0,
    )
    assert io_stub.file_reads == ["map.json"]
    assert io_stub.stdin_reads == 0
    assert_no_writes(io_stub)


@pytest.mark.parametrize(
    ("selected_line", "expected"),
    [
        (
            1,
            (
                (
                    "line  col  source  oline  ocol  name\n"
                    '1     1    "a.ts"  1      1     "n"\n'
                    "1     2    -       -      -     -\n"
                    "segments    2\n"
                ),
                0,
            ),
        ),
        (
            2,
            (
                (
                    "line  col  source  oline  ocol  name\n"
                    "2     1    -       -      -     -\n"
                    "segments    1\n"
                ),
                0,
            ),
        ),
        (3, ("line  col  source  oline  ocol  name\nsegments    0\n", 0)),
        (
            4,
            (
                (
                    "line  col  source  oline  ocol  name\n"
                    '4     1    "a.ts"  1      1     -\n'
                    "segments    1\n"
                ),
                0,
            ),
        ),
        (1000000, ("line  col  source  oline  ocol  name\nsegments    0\n", 0)),
    ],
)
def test_decode_selects_only_requested_line_and_recomputes_widths(
    selected_line: int, expected: tuple[str, int]
) -> None:
    io_stub = MemoryIO(
        files={
            "map.json": (
                b'{"version":3,"sources":["a.ts"],"names":["n"],"mappings":"AAAAA,C;A;;AAAA"}'
            )
        }
    )

    assert cmd_decode.run_decode(["map.json"], {"--line": selected_line}, io_stub) == expected
    assert io_stub.file_reads == ["map.json"]
    assert io_stub.stdin_reads == 0
    assert_no_writes(io_stub)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--line", "1", "m"], ({"--line": 1}, ["m"])),
        (["m", "--line=1000000"], ({"--line": 1000000}, ["m"])),
        (["--line", "0", "--line=2", "m"], ({"--line": 2}, ["m"])),
    ],
)
def test_decode_line_options_accept_endpoints_and_last_value(
    argv: list[str], expected: tuple[dict[str, int | str | None], list[str]]
) -> None:
    assert parse_options(argv, cmd_decode.SPECS) == expected


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--line", "0"], 'invalid --line "0" (expected an integer from 1 to 1000000)'),
        (
            ["--line", "1000001"],
            'invalid --line "1000001" (expected an integer from 1 to 1000000)',
        ),
        (["--line"], "--line needs a value"),
    ],
)
def test_decode_line_options_reject_out_of_range_and_missing_values(
    argv: list[str], message: str
) -> None:
    with pytest.raises(Fail) as error:
        parse_options(argv, cmd_decode.SPECS)

    assert str(error.value) == message


def test_stats_preserves_duplicate_and_unused_sources_and_empty_map_counts() -> None:
    populated_io = MemoryIO(
        files={
            "map.json": (
                b'{"version":3,"sources":["a","a","unused"],"names":["n"],'
                b'"sourcesContent":["",null,"x"],"mappings":"AAAAA,CCAA,C;"}'
            )
        }
    )

    assert cmd_stats.run_stats(["map.json"], {}, populated_io) == (
        (
            "lines       2\n"
            "segments    3\n"
            "mapped      2\n"
            "sources     3\n"
            "used        2\n"
            "names       1\n"
            "named       1\n"
            "content     2\n"
            'source      "a" 1\n'
            'source      "a" 1\n'
            'source      "unused" 0\n'
        ),
        0,
    )
    assert populated_io.file_reads == ["map.json"]
    assert populated_io.stdin_reads == 0
    assert_no_writes(populated_io)

    empty_io = MemoryIO(files={"empty.json": b'{"version":3,"sources":[],"mappings":""}'})

    assert cmd_stats.run_stats(["empty.json"], {}, empty_io) == (
        (
            "lines       1\n"
            "segments    0\n"
            "mapped      0\n"
            "sources     0\n"
            "used        0\n"
            "names       0\n"
            "named       0\n"
            "content     0\n"
        ),
        0,
    )
    assert empty_io.file_reads == ["empty.json"]
    assert empty_io.stdin_reads == 0
    assert_no_writes(empty_io)


def test_decode_and_stats_render_nonprintable_source_and_name_text_safely() -> None:
    document = (
        b'{"version":3,"sources":["a\\n\xce\xa9"],"names":["n\\t\xce\xa9"],"mappings":"AAAAA"}'
    )
    decode_io = MemoryIO(files={"map.json": document})

    assert cmd_decode.run_decode(["map.json"], {"--line": None}, decode_io) == (
        (
            "line  col  source  oline  ocol  name\n"
            '1     1    "a??"   1      1     "n??"\n'
            "segments    1\n"
        ),
        0,
    )
    assert decode_io.file_reads == ["map.json"]
    assert decode_io.stdin_reads == 0
    assert_no_writes(decode_io)

    stats_io = MemoryIO(files={"map.json": document})

    assert cmd_stats.run_stats(["map.json"], {}, stats_io) == (
        (
            "lines       1\n"
            "segments    1\n"
            "mapped      1\n"
            "sources     1\n"
            "used        1\n"
            "names       1\n"
            "named       1\n"
            "content     0\n"
            'source      "a??" 1\n'
        ),
        0,
    )
    assert stats_io.file_reads == ["map.json"]
    assert stats_io.stdin_reads == 0
    assert_no_writes(stats_io)


@pytest.mark.parametrize(
    ("runner", "options", "expected"),
    [
        (cmd_check.run_check, {}, ("ok, 1 segment\n", 0)),
        (
            cmd_decode.run_decode,
            {"--line": None},
            (
                (
                    "line  col  source  oline  ocol  name\n1     1    -       -      -     -\nsegments    1\n"
                ),
                0,
            ),
        ),
        (
            cmd_stats.run_stats,
            {},
            (
                (
                    "lines       1\n"
                    "segments    1\n"
                    "mapped      0\n"
                    "sources     0\n"
                    "used        0\n"
                    "names       0\n"
                    "named       0\n"
                    "content     0\n"
                ),
                0,
            ),
        ),
    ],
)
def test_all_adapters_read_valid_map_from_stdin_without_writing(
    runner, options: dict, expected: tuple[str, int]
) -> None:
    io_stub = MemoryIO(stdin=b'{"version":3,"sources":[],"mappings":"A"}')

    assert runner(["-"], options, io_stub) == expected
    assert io_stub.stdin_reads == 1
    assert io_stub.file_reads == []
    assert_no_writes(io_stub)


@pytest.mark.parametrize(
    ("runner", "options"),
    [
        (cmd_check.run_check, {}),
        (cmd_decode.run_decode, {"--line": None}),
        (cmd_stats.run_stats, {}),
    ],
)
@pytest.mark.parametrize(
    ("argument", "file_value", "stdin_value", "message"),
    [
        (
            "nowhere.map",
            OSError("missing"),
            b"",
            '"nowhere.map": cannot read the file',
        ),
        ("bad.json", b"{", b"", '"bad.json": not valid JSON'),
        ("list.json", b"[]", b"", '"list.json": the top level is not an object'),
        ("-", None, b"AB\xff\n", "<stdin>: input is not valid UTF-8"),
    ],
)
def test_all_adapters_propagate_input_json_and_utf8_failures(
    runner,
    options: dict,
    argument: str,
    file_value: bytes | OSError | None,
    stdin_value: bytes,
    message: str,
) -> None:
    files = {} if argument == "-" else {argument: file_value}
    io_stub = MemoryIO(files=files, stdin=stdin_value)

    with pytest.raises(Fail) as error:
        runner([argument], options, io_stub)

    assert str(error.value) == message
    assert io_stub.file_reads == ([] if argument == "-" else [argument])
    assert io_stub.stdin_reads == (1 if argument == "-" else 0)
    assert_no_writes(io_stub)


@pytest.mark.parametrize(
    ("runner", "argument", "document", "expected"),
    [
        (
            cmd_check.run_check,
            "bang.map",
            b'{"version":3,"sources":["a"],"mappings":"AAA!"}',
            ('SM101 invalid character "!" at character 4\n1 problem\n', 1),
        ),
        (
            cmd_decode.run_decode,
            "bang.map",
            b'{"version":3,"sources":["a"],"mappings":"AAA!"}',
            '"bang.map": SM101 invalid character "!" at character 4',
        ),
        (
            cmd_stats.run_stats,
            "bang.map",
            b'{"version":3,"sources":["a"],"mappings":"AAA!"}',
            '"bang.map": SM101 invalid character "!" at character 4',
        ),
        (
            cmd_check.run_check,
            "multi.map",
            b'{"version":2}',
            (
                (
                    "SM001 version must be 3\n"
                    "SM003 sources must be an array of strings\n"
                    "SM006 mappings must be a string\n"
                    "3 problems\n"
                ),
                1,
            ),
        ),
        (
            cmd_decode.run_decode,
            "multi.map",
            b'{"version":2}',
            '"multi.map": SM001 version must be 3',
        ),
        (
            cmd_stats.run_stats,
            "multi.map",
            b'{"version":2}',
            '"multi.map": SM001 version must be 3',
        ),
    ],
)
def test_check_lists_mapping_problems_while_decode_and_stats_fail_first(
    runner, argument: str, document: bytes, expected: tuple[str, int] | str
) -> None:
    io_stub = MemoryIO(files={argument: document})

    if isinstance(expected, tuple):
        assert runner([argument], {"--line": None}, io_stub) == expected
    else:
        with pytest.raises(Fail) as error:
            runner([argument], {"--line": None}, io_stub)
        assert str(error.value) == expected

    assert io_stub.file_reads == [argument]
    assert io_stub.stdin_reads == 0
    assert_no_writes(io_stub)
