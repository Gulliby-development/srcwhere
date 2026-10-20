import json

from srcwhere.base.fail import Fail
from srcwhere.base.inputs import IO, read_text
from srcwhere.smap.model import Problem, SourceMap
from srcwhere.smap.structure import document_problems


def _reject_constant(value: str) -> None:
    raise ValueError(value)


def read_document(io: IO, arg: str) -> tuple[str, dict]:
    """Read one JSON object and preserve its safe display name."""
    display, text = read_text(io, arg)
    try:
        document = json.loads(text, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as error:
        raise Fail(f"{display}: not valid JSON") from error

    if not isinstance(document, dict):
        raise Fail(f"{display}: the top level is not an object")
    return display, document


def load_problems(io: IO, arg: str) -> tuple[str, list[Problem], SourceMap | None]:
    """Read and structurally validate one source map document."""
    display, document = read_document(io, arg)
    problems, source_map = document_problems(document)
    return display, problems, source_map


def load_map(io: IO, arg: str) -> SourceMap:
    """Load a valid source map or raise the first structural problem."""
    display, problems, source_map = load_problems(io, arg)
    if problems:
        raise Fail(f"{display}: {problems[0].format()}")
    if source_map is None:
        raise RuntimeError("document validation returned no map")
    return source_map
