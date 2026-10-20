import pytest

from srcwhere.base.fail import Fail
from srcwhere.smap import loader
from srcwhere.smap.model import Problem, Segment, SourceMap


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


def test_read_document_selects_only_named_file_and_keeps_last_duplicate_key() -> None:
    io_stub = MemoryIO(
        files={"map.json": b'{"version":2,"version":3,"nested":{"items":[1,true,null]}}'}
    )

    display, document = loader.read_document(io_stub, "map.json")

    assert display == '"map.json"'
    assert document == {"version": 3, "nested": {"items": [1, True, None]}}
    assert io_stub.file_reads == ["map.json"]
    assert io_stub.stdin_reads == 0
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_read_document_selects_stdin_once() -> None:
    io_stub = MemoryIO(stdin=b'{"version":3,"sources":[]}')

    display, document = loader.read_document(io_stub, "-")

    assert (display, document) == ("<stdin>", {"version": 3, "sources": []})
    assert io_stub.stdin_reads == 1
    assert io_stub.file_reads == []
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_read_document_removes_one_leading_bom_but_rejects_a_second() -> None:
    io_stub = MemoryIO(
        files={
            "single.json": b'\xef\xbb\xbf{"version":3}',
            "double.json": b"\xef\xbb\xbf\xef\xbb\xbf{}",
        }
    )

    assert loader.read_document(io_stub, "single.json") == (
        '"single.json"',
        {"version": 3},
    )
    with pytest.raises(Fail) as error:
        loader.read_document(io_stub, "double.json")

    assert str(error.value) == '"double.json": not valid JSON'
    assert io_stub.file_reads == ["single.json", "double.json"]
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_read_document_preserves_read_errors_and_safe_display_names() -> None:
    io_stub = MemoryIO(
        files={
            "nowhere.map": OSError("not found"),
            "bad\nmap": b'{"version":3}',
        }
    )

    with pytest.raises(Fail) as error:
        loader.read_document(io_stub, "nowhere.map")
    assert str(error.value) == '"nowhere.map": cannot read the file'

    assert loader.read_document(io_stub, "bad\nmap") == (
        '"bad?map"',
        {"version": 3},
    )
    assert io_stub.file_reads == ["nowhere.map", "bad\nmap"]
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_read_document_rejects_malformed_utf8_bytes() -> None:
    stdin_io = MemoryIO(stdin=bytes.fromhex("41 42 FF 0A"))
    with pytest.raises(Fail) as error:
        loader.read_document(stdin_io, "-")
    assert str(error.value) == "<stdin>: input is not valid UTF-8"
    assert stdin_io.stdin_reads == 1
    assert stdin_io.file_reads == []

    file_io = MemoryIO(files={"bad.map": b"\x41\x42\xff\x0a"})
    with pytest.raises(Fail) as error:
        loader.read_document(file_io, "bad.map")
    assert str(error.value) == '"bad.map": input is not valid UTF-8'
    assert file_io.file_reads == ["bad.map"]
    assert file_io.outputs == []
    assert file_io.errors == []


@pytest.mark.parametrize(
    "text",
    [
        "{",
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":-Infinity}',
    ],
)
def test_read_document_rejects_malformed_json_and_nonfinite_constants(text: str) -> None:
    io_stub = MemoryIO(files={"bad.json": text.encode("utf-8")})

    with pytest.raises(Fail) as error:
        loader.read_document(io_stub, "bad.json")

    assert str(error.value) == '"bad.json": not valid JSON'
    assert io_stub.file_reads == ["bad.json"]
    assert io_stub.outputs == []
    assert io_stub.errors == []


@pytest.mark.parametrize("exception", [RecursionError("too deep"), ValueError("too many digits")])
def test_read_document_translates_parser_failures(
    monkeypatch: pytest.MonkeyPatch, exception: Exception
) -> None:
    io_stub = MemoryIO(files={"bad.json": b"{}"})

    def fail_to_parse(text: str, **kwargs: object) -> object:
        assert text == "{}"
        assert "parse_constant" in kwargs
        raise exception

    monkeypatch.setattr(loader.json, "loads", fail_to_parse)

    with pytest.raises(Fail) as error:
        loader.read_document(io_stub, "bad.json")

    assert str(error.value) == '"bad.json": not valid JSON'
    assert io_stub.file_reads == ["bad.json"]
    assert io_stub.outputs == []
    assert io_stub.errors == []


@pytest.mark.parametrize(
    "text",
    [
        "[]",
        '"text"',
        "3",
        "true",
        "null",
    ],
)
def test_read_document_rejects_each_kind_of_valid_non_object_root(text: str) -> None:
    io_stub = MemoryIO(files={"root.json": text.encode("utf-8")})

    with pytest.raises(Fail) as error:
        loader.read_document(io_stub, "root.json")

    assert str(error.value) == '"root.json": the top level is not an object'
    assert io_stub.file_reads == ["root.json"]


def test_read_document_preserves_valid_nested_json_values() -> None:
    io_stub = MemoryIO(
        files={
            "nested.json": (
                b'{"version":3,"array":[1,-2.5,true,false,null,"text"],'
                b'"object":{"empty":[],"child":{"key":"value"}}}'
            )
        }
    )

    display, document = loader.read_document(io_stub, "nested.json")

    assert display == '"nested.json"'
    assert document == {
        "version": 3,
        "array": [1, -2.5, True, False, None, "text"],
        "object": {"empty": [], "child": {"key": "value"}},
    }
    assert io_stub.file_reads == ["nested.json"]


def test_load_problems_returns_ordered_validation_results() -> None:
    io_stub = MemoryIO(files={"bad.map": b"{}"})

    display, problems, source_map = loader.load_problems(io_stub, "bad.map")

    assert display == '"bad.map"'
    assert problems == [
        Problem("SM001", "version must be 3"),
        Problem("SM003", "sources must be an array of strings"),
        Problem("SM006", "mappings must be a string"),
    ]
    assert source_map is None
    assert io_stub.file_reads == ["bad.map"]
    assert io_stub.outputs == []
    assert io_stub.errors == []


def test_load_map_returns_valid_map_or_only_the_first_problem() -> None:
    valid_io = MemoryIO(
        files={
            "good.map": (
                b'{"version":3,"file":"app.js","sources":["a.ts"],"names":["n"],'
                b'"sourcesContent":["text"],"mappings":"AAAAA"}'
            )
        }
    )
    assert loader.load_map(valid_io, "good.map") == SourceMap(
        "app.js",
        ["a.ts"],
        ["n"],
        ["text"],
        [[Segment(0, 0, 0, 0, 0)]],
    )
    assert valid_io.file_reads == ["good.map"]
    assert valid_io.outputs == []
    assert valid_io.errors == []

    invalid_io = MemoryIO(files={"bad.map": b'{"version":2,"sources":false,"mappings":false}'})
    with pytest.raises(Fail) as error:
        loader.load_map(invalid_io, "bad.map")
    assert str(error.value) == '"bad.map": SM001 version must be 3'
    assert invalid_io.file_reads == ["bad.map"]
    assert invalid_io.outputs == []
    assert invalid_io.errors == []


def test_loader_adapters_propagate_input_and_json_failures_unchanged() -> None:
    missing_problems_io = MemoryIO(files={"missing.map": OSError("not found")})
    with pytest.raises(Fail) as error:
        loader.load_problems(missing_problems_io, "missing.map")
    assert str(error.value) == '"missing.map": cannot read the file'
    assert missing_problems_io.file_reads == ["missing.map"]
    assert missing_problems_io.outputs == []
    assert missing_problems_io.errors == []

    missing_map_io = MemoryIO(files={"missing.map": OSError("not found")})
    with pytest.raises(Fail) as error:
        loader.load_map(missing_map_io, "missing.map")
    assert str(error.value) == '"missing.map": cannot read the file'
    assert missing_map_io.file_reads == ["missing.map"]
    assert missing_map_io.outputs == []
    assert missing_map_io.errors == []

    malformed_problems_io = MemoryIO(files={"bad.json": b'{"x":NaN}'})
    with pytest.raises(Fail) as error:
        loader.load_problems(malformed_problems_io, "bad.json")
    assert str(error.value) == '"bad.json": not valid JSON'
    assert malformed_problems_io.file_reads == ["bad.json"]
    assert malformed_problems_io.outputs == []
    assert malformed_problems_io.errors == []

    malformed_map_io = MemoryIO(files={"bad.json": b'{"x":NaN}'})
    with pytest.raises(Fail) as error:
        loader.load_map(malformed_map_io, "bad.json")
    assert str(error.value) == '"bad.json": not valid JSON'
    assert malformed_map_io.file_reads == ["bad.json"]
    assert malformed_map_io.outputs == []
    assert malformed_map_io.errors == []
