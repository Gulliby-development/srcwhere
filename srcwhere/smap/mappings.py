from srcwhere.base.fail import Fail
from srcwhere.smap.model import Problem, Segment
from srcwhere.vlq.stream import decode_numbers


def _decode_problem(error: Fail) -> Problem:
    text = str(error)
    if text.startswith("invalid character "):
        return Problem("SM101", text)
    if text.startswith("incomplete number "):
        return Problem("SM102", text)
    return Problem("SM111", text)


def decode_mappings(
    text: str, nsources: int, nnames: int
) -> tuple[list[list[Segment]], Problem | None]:
    lines: list[list[Segment]] = []
    source_index = 0
    original_line = 0
    original_column = 0
    name_index = 0
    absolute_line_start = 0

    for line_text in text.split(";"):
        decoded_line: list[Segment] = []
        generated_column = 0
        segment_start = 0

        for segment_text in line_text.split(","):
            if segment_text:
                try:
                    fields = decode_numbers(segment_text, absolute_line_start + segment_start)
                except Fail as error:
                    return lines, _decode_problem(error)

                if len(fields) not in (1, 4, 5):
                    return lines, Problem(
                        "SM103",
                        f"segment has {len(fields)} fields (expected 1, 4 or 5) "
                        f"at character {absolute_line_start + segment_start + 1}",
                    )

                generated_delta, generated_position = fields[0]
                next_generated_column = generated_column + generated_delta
                if next_generated_column < 0:
                    return lines, Problem(
                        "SM104",
                        f"generated column {next_generated_column} is negative "
                        f"at character {generated_position}",
                    )
                if next_generated_column < generated_column:
                    return lines, Problem(
                        "SM110",
                        f"generated column {next_generated_column} is before column "
                        f"{generated_column} of the previous segment "
                        f"at character {generated_position}",
                    )
                generated_column = next_generated_column

                if len(fields) >= 4:
                    source_index += fields[1][0]
                    if source_index < 0 or source_index >= nsources:
                        return lines, Problem(
                            "SM105",
                            f"source index {source_index} is out of range "
                            f"(sources has {nsources}) at character {fields[1][1]}",
                        )

                    original_line += fields[2][0]
                    if original_line < 0:
                        return lines, Problem(
                            "SM106",
                            f"original line {original_line} is negative "
                            f"at character {fields[2][1]}",
                        )

                    original_column += fields[3][0]
                    if original_column < 0:
                        return lines, Problem(
                            "SM107",
                            f"original column {original_column} is negative "
                            f"at character {fields[3][1]}",
                        )

                    decoded_name: int | None = None
                    if len(fields) == 5:
                        name_index += fields[4][0]
                        if name_index < 0 or name_index >= nnames:
                            return lines, Problem(
                                "SM108",
                                f"name index {name_index} is out of range "
                                f"(names has {nnames}) at character {fields[4][1]}",
                            )
                        decoded_name = name_index

                    decoded_line.append(
                        Segment(
                            generated_column,
                            source_index,
                            original_line,
                            original_column,
                            decoded_name,
                        )
                    )
                else:
                    decoded_line.append(Segment(generated_column, None, None, None, None))

            segment_start += len(segment_text) + 1

        lines.append(decoded_line)
        absolute_line_start += len(line_text) + 1

    return lines, None
