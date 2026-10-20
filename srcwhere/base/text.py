def show(text: str) -> str:
    """Quote text while replacing non-ASCII-printable code points with question marks."""
    displayed = "".join(character if " " <= character <= "~" else "?" for character in text)
    return f'"{displayed}"'


def line(key: str, value: str) -> str:
    """Format a labeled output line using a ten-character minimum key width."""
    return f"{key:<10}  {value}\n"


def table(header: list[str], rows: list[list[str]]) -> str:
    """Render a left-aligned table with two-space separators and no trailing spaces."""
    all_rows = [header, *rows]
    column_count = max((len(row) for row in all_rows), default=0)
    widths = [
        max((len(row[index]) for row in all_rows if index < len(row)), default=0)
        for index in range(column_count)
    ]

    rendered = []
    for row in all_rows:
        cells = [
            (row[index] if index < len(row) else "").ljust(widths[index])
            for index in range(column_count)
        ]
        rendered.append("  ".join(cells).rstrip(" ") + "\n")
    return "".join(rendered)


def plural(n: int, word: str) -> str:
    """Return a count followed by the singular or plural form of a word."""
    suffix = "" if n == 1 else "s"
    return f"{n} {word}{suffix}"
