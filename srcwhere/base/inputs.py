import sys
from typing import Protocol

from srcwhere.base.fail import Fail
from srcwhere.base.text import show


class IO(Protocol):
    """The byte-oriented input and text-output boundary used by commands."""

    def read_stdin(self) -> bytes:
        """Read all bytes from standard input."""
        ...

    def read_file(self, path: str) -> bytes:
        """Read all bytes from a named file."""
        ...

    def out(self, text: str) -> None:
        """Write text to standard output."""
        ...

    def err(self, text: str) -> None:
        """Write text to standard error."""
        ...


class StdIO:
    """Use binary standard streams and binary file access for real IO."""

    def read_stdin(self) -> bytes:
        return sys.stdin.buffer.read()

    def read_file(self, path: str) -> bytes:
        with open(path, "rb") as input_file:
            return input_file.read()

    def out(self, text: str) -> None:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))

    def err(self, text: str) -> None:
        sys.stderr.buffer.write(text.encode("utf-8", errors="replace"))


def read_text(io: IO, arg: str) -> tuple[str, str]:
    """Read and strictly decode stdin or a named UTF-8 file."""
    display = "<stdin>" if arg == "-" else show(arg)
    try:
        data = io.read_stdin() if arg == "-" else io.read_file(arg)
    except OSError as error:
        raise Fail(f"{display}: cannot read the file") from error

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Fail(f"{display}: input is not valid UTF-8") from error

    return display, text.removeprefix("\ufeff")
