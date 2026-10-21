"""Remap matching stack frames through a source map."""

from srcwhere.query.lookup import find_segment
from srcwhere.smap.model import SourceMap
from srcwhere.trace.frames import Frame, parse_frame, render_frame


def remap_trace(sm: SourceMap, text: str, name: str) -> tuple[str, int]:
    """Rewrite frames for the requested name and count matching unmapped frames."""
    rewritten: list[str] = []
    unmapped = 0

    for piece in text.split("\n"):
        has_cr = piece.endswith("\r")
        line = piece[:-1] if has_cr else piece
        frame = parse_frame(line)

        if frame is None or not (frame.file == name or frame.file.endswith("/" + name)):
            rewritten.append(piece)
            continue

        segment = find_segment(sm, frame.line - 1, frame.col - 1)
        if segment is None:
            unmapped += 1
            rewritten.append(piece)
            continue

        func = frame.func
        if func and segment.name is not None:
            mapped_name = sm.names[segment.name]
            if frame.kind == "v8":
                prefix = ""
                remainder = func
                for marker in ("async ", "new "):
                    if remainder.startswith(marker) and len(remainder) > len(marker):
                        prefix += marker
                        remainder = remainder[len(marker) :]
                func = prefix + mapped_name
            else:
                func = mapped_name

        remapped = Frame(
            kind=frame.kind,
            indent=frame.indent,
            func=func,
            file=sm.sources[segment.source],
            line=segment.line + 1,
            col=segment.column + 1,
        )
        rendered = render_frame(remapped)
        rewritten.append(rendered + ("\r" if has_cr else ""))

    return "\n".join(rewritten), unmapped
