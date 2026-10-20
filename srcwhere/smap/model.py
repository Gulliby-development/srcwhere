from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    col: int
    source: int | None
    line: int | None
    column: int | None
    name: int | None


@dataclass
class SourceMap:
    file: str | None
    sources: list[str]
    names: list[str]
    contents: list[str | None]
    lines: list[list[Segment]]


@dataclass(frozen=True)
class Problem:
    code: str
    text: str

    def format(self) -> str:
        return f"{self.code} {self.text}"
