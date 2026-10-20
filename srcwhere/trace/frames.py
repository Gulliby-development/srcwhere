"""Parse and render the supported JavaScript stack-frame forms."""

import re
from dataclasses import dataclass

_LOCATION = r"([^ \t()]+):([1-9][0-9]{0,6}):([1-9][0-9]{0,6})"
_INDENT = r"([ \t]*)"


@dataclass(frozen=True)
class Frame:
    """One parsed stack frame, with its original one-based position."""

    kind: str
    indent: str
    func: str | None
    file: str
    line: int
    col: int


def parse_frame(text: str) -> Frame | None:
    """Parse a complete frame in v8, bare-v8, then gecko priority order."""
    any_chars = r"[\s\S]"

    match = re.fullmatch(
        _INDENT + r"at " + f"({any_chars}+)" + r" \(" + _LOCATION + r"\)",
        text,
    )
    if match is not None:
        indent, func, file, line, col = match.groups()
        return Frame("v8", indent, func, file, int(line), int(col))

    match = re.fullmatch(_INDENT + r"at " + _LOCATION, text)
    if match is not None:
        indent, file, line, col = match.groups()
        return Frame("v8bare", indent, None, file, int(line), int(col))

    match = re.fullmatch(f"([^@]*)@{_LOCATION}", text)
    if match is not None:
        func, file, line, col = match.groups()
        return Frame("gecko", "", func, file, int(line), int(col))

    return None


def render_frame(frame: Frame) -> str:
    """Render a valid frame in its original syntax without a line ending."""
    location = f"{frame.file}:{frame.line}:{frame.col}"
    if frame.kind == "v8":
        return f"{frame.indent}at {frame.func} ({location})"
    if frame.kind == "v8bare":
        return f"{frame.indent}at {location}"
    if frame.kind == "gecko":
        return f"{frame.func}@{location}"
    raise ValueError(f"unsupported frame kind: {frame.kind}")
