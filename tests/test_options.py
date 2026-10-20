import builtins
import io
import sys
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from srcwhere.base.fail import Fail
from srcwhere.base.inputs import StdIO, read_text
from srcwhere.base.options import Spec, parse_options


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
        value = self.files[path]
        if isinstance(value, OSError):
            raise value
        return value

    def out(self, text: str) -> None:
        self.outputs.append(text)

    def err(self, text: str) -> None:
        self.errors.append(text)


def test_spec_defaults_and_frozen_behavior() -> None:
    file_spec = Spec("--file")
    line_spec = Spec("--line", True, 1, 1000000)

    assert (file_spec.name, file_spec.numeric, file_spec.lo, file_spec.hi) == (
        "--file",
        False,
        0,
        0,
    )
    assert (line_spec.name, line_spec.numeric, line_spec.lo, line_spec.hi) == (
        "--line",
        True,
        1,
        1000000,
    )
    with pytest.raises(FrozenInstanceError):
        file_spec.name = "--other"


def test_parse_options_absent_values_and_ordinary_arguments() -> None:
    specs = [Spec("--line", True, 1, 1000000), Spec("--file")]

    assert parse_options([], specs) == (
        {"--line": None, "--file": None},
        [],
    )
    assert parse_options(["a", "--line=2", "-", "-5"], specs) == (
        {"--line": 2, "--file": None},
        ["a", "-", "-5"],
    )


def test_parse_options_accepts_inline_values_and_splits_at_first_equals() -> None:
    specs = [Spec("--line", True, 1, 1000000), Spec("--file")]

    assert parse_options(["--line=2", "--file=a=b"], specs) == (
        {"--line": 2, "--file": "a=b"},
        [],
    )


def test_parse_options_consumes_the_next_token_even_when_it_starts_with_dashes() -> None:
    specs = [Spec("--line", True, 1, 1000000), Spec("--file")]

    assert parse_options(["--file", "--help"], specs) == (
        {"--line": None, "--file": "--help"},
        [],
    )


def test_parse_options_uses_the_last_value_for_repeated_options() -> None:
    specs = [Spec("--line", True, 1, 1000000), Spec("--file")]

    assert parse_options(
        ["--line", "bad", "--line=3", "--file=first", "--file", "second"],
        specs,
    ) == ({"--line": 3, "--file": "second"}, [])


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--line=bad", "--x"], 'unknown option "--x"'),
        (["--line=bad", "--file"], "--file needs a value"),
        (["--file="], "--file needs a value"),
        (["--file", ""], "--file needs a value"),
        (["--"], 'unknown option "--"'),
        (["--help"], 'unknown option "--help"'),
        (["--x=value"], 'unknown option "--x=value"'),
    ],
)
def test_parse_options_reports_syntax_errors_before_numeric_validation(
    argv: list[str], expected: str
) -> None:
    specs = [Spec("--line", True, 1, 1000000), Spec("--file")]

    with pytest.raises(Fail) as error:
        parse_options(argv, specs)

    assert str(error.value) == expected


def test_parse_options_validates_numeric_values_in_spec_order() -> None:
    specs = [Spec("--first", True, 0, 10), Spec("--second", True, 0, 10)]

    assert parse_options(["--first=0", "--second=10"], specs) == (
        {"--first": 0, "--second": 10},
        [],
    )
    with pytest.raises(Fail) as error:
        parse_options(["--second=bad", "--first=bad"], specs)
    assert str(error.value) == ('invalid --first "bad" (expected an integer from 0 to 10)')

    with pytest.raises(Fail) as error:
        parse_options(["--line=0"], [Spec("--line", True, 1, 1000000)])
    assert str(error.value) == ('invalid --line "0" (expected an integer from 1 to 1000000)')


def test_read_text_decodes_stdin_and_preserves_exact_file_text() -> None:
    io_stub = MemoryIO(
        stdin=b"hello\r\n",
        files={
            "a.map": b"\xef\xbb\xbfhello",
            "two.map": b"\xef\xbb\xbf\xef\xbb\xbfdata",
            "embedded.map": b"a\xef\xbb\xbfb",
            "empty.map": b"",
            "unicode.map": "caf\u00e9".encode("utf-8"),
            "new\nline.map": b"safe",
        },
    )

    assert read_text(io_stub, "-") == ("<stdin>", "hello\r\n")
    assert read_text(io_stub, "a.map") == ('"a.map"', "hello")
    assert read_text(io_stub, "two.map") == ('"two.map"', "\ufeffdata")
    assert read_text(io_stub, "embedded.map") == ('"embedded.map"', "a\ufeffb")
    assert read_text(io_stub, "empty.map") == ('"empty.map"', "")
    assert read_text(io_stub, "unicode.map") == ('"unicode.map"', "caf\u00e9")
    assert read_text(io_stub, "new\nline.map") == ('"new?line.map"', "safe")
    assert io_stub.stdin_reads == 1
    assert io_stub.file_reads == [
        "a.map",
        "two.map",
        "embedded.map",
        "empty.map",
        "unicode.map",
        "new\nline.map",
    ]


def test_read_text_reports_utf8_and_os_errors_for_stdin_and_files() -> None:
    bad_stdin = MemoryIO(stdin=b"AB\xff\n")
    with pytest.raises(Fail) as error:
        read_text(bad_stdin, "-")
    assert str(error.value) == "<stdin>: input is not valid UTF-8"
    assert bad_stdin.stdin_reads == 1

    bad_file = MemoryIO(files={"bad.map": b"AB\xff\n"})
    with pytest.raises(Fail) as error:
        read_text(bad_file, "bad.map")
    assert str(error.value) == '"bad.map": input is not valid UTF-8'
    assert bad_file.file_reads == ["bad.map"]

    stdin_os_error = MemoryIO(stdin=OSError("stdin unavailable"))
    with pytest.raises(Fail) as error:
        read_text(stdin_os_error, "-")
    assert str(error.value) == "<stdin>: cannot read the file"

    missing_file = MemoryIO(files={"missing.map": OSError("not found")})
    with pytest.raises(Fail) as error:
        read_text(missing_file, "missing.map")
    assert str(error.value) == '"missing.map": cannot read the file'
    assert missing_file.file_reads == ["missing.map"]


def test_stdio_reads_stdin_bytes_without_opening_a_file(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = SimpleNamespace(buffer=io.BytesIO(b"stdin\x00bytes"))
    monkeypatch.setattr(sys, "stdin", stream)

    def unexpected_open(*args: object, **kwargs: object) -> None:
        raise AssertionError("stdin reads must not open a file")

    monkeypatch.setattr(builtins, "open", unexpected_open)

    assert StdIO().read_stdin() == b"stdin\x00bytes"


def test_stdio_reads_only_the_named_file_in_binary_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[tuple[str, str]] = []

    def memory_open(path: str, mode: str) -> io.BytesIO:
        opened.append((path, mode))
        return io.BytesIO(b"named\r\nbytes")

    monkeypatch.setattr(builtins, "open", memory_open)

    assert StdIO().read_file("only.map") == b"named\r\nbytes"
    assert opened == [("only.map", "rb")]


def test_stdio_writes_utf8_replacement_bytes_without_extra_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout_buffer = io.BytesIO()
    stderr_buffer = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=stdout_buffer))
    monkeypatch.setattr(sys, "stderr", SimpleNamespace(buffer=stderr_buffer))

    stdio = StdIO()
    stdio.out("é\n\ud800")
    stdio.err("error\n")

    assert stdout_buffer.getvalue() == b"\xc3\xa9\n?"
    assert stderr_buffer.getvalue() == b"error\n"
