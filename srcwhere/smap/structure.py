from srcwhere.smap.mappings import decode_mappings
from srcwhere.smap.model import Problem, SourceMap
from srcwhere.smap.sections import merge


def _regular_problems(
    doc: dict,
) -> tuple[list[Problem], SourceMap | None]:
    problems: list[Problem] = []

    version = doc.get("version")
    if type(version) is not int or version != 3:
        problems.append(Problem("SM001", "version must be 3"))

    file = doc.get("file")
    if "file" in doc and not isinstance(file, str):
        problems.append(Problem("SM002", "file must be a string"))
        file = None

    sources = doc.get("sources")
    sources_valid = isinstance(sources, list) and all(isinstance(source, str) for source in sources)
    if not sources_valid:
        problems.append(Problem("SM003", "sources must be an array of strings"))
        sources = []

    names = doc.get("names", [])
    names_valid = isinstance(names, list) and all(isinstance(name, str) for name in names)
    if "names" in doc and not names_valid:
        problems.append(Problem("SM004", "names must be an array of strings"))
        names = []
    elif not names_valid:
        names = []

    contents = doc.get("sourcesContent")
    contents_valid = isinstance(contents, list) and all(
        content is None or isinstance(content, str) for content in contents
    )
    if "sourcesContent" in doc and not contents_valid:
        problems.append(Problem("SM005", "sourcesContent must be an array of strings or null"))
        contents = []

    mappings = doc.get("mappings")
    mappings_valid = isinstance(mappings, str)
    if not mappings_valid:
        problems.append(Problem("SM006", "mappings must be a string"))

    decoded_lines: list[list] = []
    if sources_valid and names_valid and mappings_valid:
        decoded_lines, mapping_problem = decode_mappings(mappings, len(sources), len(names))
        if mapping_problem is not None:
            problems.append(mapping_problem)

    if problems:
        return problems, None

    if not contents_valid:
        contents = []
    source_contents = list(contents[: len(sources)])
    source_contents.extend([None] * (len(sources) - len(source_contents)))
    return (
        [],
        SourceMap(
            file,
            list(sources),
            list(names),
            source_contents,
            decoded_lines,
        ),
    )


def document_problems(doc: dict) -> tuple[list[Problem], SourceMap | None]:
    """Validate a regular or indexed source map document."""
    if "sections" not in doc:
        return _regular_problems(doc)

    problems: list[Problem] = []
    version = doc.get("version")
    if type(version) is not int or version != 3:
        problems.append(Problem("SM001", "version must be 3"))

    file = doc.get("file")
    if "file" in doc and not isinstance(file, str):
        problems.append(Problem("SM002", "file must be a string"))
        file = None

    sections = doc.get("sections")
    if not isinstance(sections, list):
        problems.append(Problem("SM007", "sections must be an array"))
        return problems, None

    parts: list[tuple[int, int, SourceMap]] = []
    for index, section in enumerate(sections, start=1):
        section_is_object = isinstance(section, dict)
        offset = section.get("offset") if section_is_object else None
        offset_valid = (
            isinstance(offset, dict)
            and type(offset.get("line")) is int
            and offset["line"] >= 0
            and type(offset.get("column")) is int
            and offset["column"] >= 0
        )
        if not offset_valid:
            problems.append(
                Problem(
                    "SM008",
                    f"section {index}: offset must be an object with integer "
                    "line and column of 0 or more",
                )
            )

        child = section.get("map") if section_is_object else None
        if not isinstance(child, dict):
            problems.append(Problem("SM009", f"section {index}: map must be an object"))
            continue

        child_problems, child_map = _regular_problems(child)
        problems.extend(
            Problem(problem.code, f"section {index}: {problem.text}") for problem in child_problems
        )
        if offset_valid and child_map is not None and not child_problems:
            parts.append((offset["line"], offset["column"], child_map))

    if problems:
        return problems, None
    return [], merge(file, parts)
