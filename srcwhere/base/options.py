from dataclasses import dataclass

from srcwhere.base.fail import Fail
from srcwhere.base.ints import parse_int
from srcwhere.base.text import show


@dataclass(frozen=True)
class Spec:
    """Describe one accepted command-line option."""

    name: str
    numeric: bool = False
    lo: int = 0
    hi: int = 0


def parse_options(
    argv: list[str], specs: list[Spec]
) -> tuple[dict[str, int | str | None], list[str]]:
    """Scan options in order, then validate the final values of numeric options."""
    by_name = {spec.name: spec for spec in specs}
    values: dict[str, int | str | None] = {spec.name: None for spec in specs}
    ordinary: list[str] = []

    index = 0
    while index < len(argv):
        argument = argv[index]
        if not argument.startswith("--"):
            ordinary.append(argument)
            index += 1
            continue

        option = argument
        if "=" in option:
            name, value = option.split("=", 1)
            has_inline_value = True
        else:
            name = option
            has_inline_value = False
            value = ""

        spec = by_name.get(name)
        if spec is None:
            raise Fail(f"unknown option {show(argument)}")

        if has_inline_value:
            if value == "":
                raise Fail(f"{name} needs a value")
        else:
            index += 1
            if index >= len(argv) or argv[index] == "":
                raise Fail(f"{name} needs a value")
            value = argv[index]

        values[name] = value
        index += 1

    for spec in specs:
        value = values[spec.name]
        if spec.numeric and value is not None:
            values[spec.name] = parse_int(spec.name, value, spec.lo, spec.hi)

    return values, ordinary
