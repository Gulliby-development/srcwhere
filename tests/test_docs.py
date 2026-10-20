from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README_PATH = ROOT / "README.md"

LAYOUT_GROUPS = {
    "package root": [
        "srcwhere/",
        "srcwhere/__init__.py",
        "srcwhere/__main__.py",
    ],
    "base": [
        "srcwhere/base/",
        "srcwhere/base/__init__.py",
        "srcwhere/base/fail.py",
        "srcwhere/base/text.py",
        "srcwhere/base/ints.py",
        "srcwhere/base/options.py",
        "srcwhere/base/inputs.py",
    ],
    "vlq": [
        "srcwhere/vlq/",
        "srcwhere/vlq/__init__.py",
        "srcwhere/vlq/codec.py",
        "srcwhere/vlq/stream.py",
    ],
    "smap": [
        "srcwhere/smap/",
        "srcwhere/smap/__init__.py",
        "srcwhere/smap/model.py",
        "srcwhere/smap/mappings.py",
        "srcwhere/smap/structure.py",
        "srcwhere/smap/sections.py",
        "srcwhere/smap/loader.py",
    ],
    "query": [
        "srcwhere/query/",
        "srcwhere/query/__init__.py",
        "srcwhere/query/lookup.py",
        "srcwhere/query/reverse.py",
        "srcwhere/query/stats.py",
    ],
    "trace": [
        "srcwhere/trace/",
        "srcwhere/trace/__init__.py",
        "srcwhere/trace/frames.py",
        "srcwhere/trace/remap.py",
    ],
    "cli": [
        "srcwhere/cli/",
        "srcwhere/cli/__init__.py",
        "srcwhere/cli/cmd_check.py",
        "srcwhere/cli/cmd_decode.py",
        "srcwhere/cli/cmd_lookup.py",
        "srcwhere/cli/cmd_reverse.py",
        "srcwhere/cli/cmd_symbolize.py",
        "srcwhere/cli/cmd_stats.py",
        "srcwhere/cli/cmd_vlq_encode.py",
        "srcwhere/cli/cmd_vlq_decode.py",
        "srcwhere/cli/cli.py",
    ],
    "tests": [
        "tests/",
        "tests/test_text.py",
        "tests/test_options.py",
        "tests/test_vlq.py",
        "tests/test_structure.py",
        "tests/test_mappings.py",
        "tests/test_loader.py",
        "tests/test_query.py",
        "tests/test_frames.py",
        "tests/test_remap.py",
        "tests/test_cmd_map.py",
        "tests/test_cmd_find.py",
        "tests/test_cmd_trace.py",
        "tests/test_cli.py",
        "tests/test_process.py",
        "tests/test_docs.py",
    ],
}


def readme_text() -> str:
    return README_PATH.read_text(encoding="utf-8")


def assert_fenced_block(readme: str, language: str, contents: str) -> None:
    assert f"```{language}\n{contents}\n```" in readme


def test_required_headings_are_present() -> None:
    readme = readme_text()
    for heading in (
        "## Install",
        "## Usage",
        "## Commands",
        "## Exit codes",
        "## Development",
        "## Layout",
    ):
        assert heading in readme.splitlines()


def test_usage_explains_repository_root_module_invocation() -> None:
    readme = readme_text()
    assert "python -m srcwhere" in readme
    assert "literal `srcwhere ...` notation" in readme


def test_help_output_has_the_exact_eight_lines() -> None:
    readme = readme_text()
    help_text = (
        "usage: srcwhere check MAP\n"
        "       srcwhere decode MAP [--line N]\n"
        "       srcwhere lookup MAP LINE:COL\n"
        "       srcwhere reverse MAP SOURCE LINE:COL\n"
        "       srcwhere symbolize MAP TRACE [--file NAME]\n"
        "       srcwhere stats MAP\n"
        "       srcwhere vlq-encode NUMBER...\n"
        "       srcwhere vlq-decode TEXT"
    )
    assert_fenced_block(readme, "text", help_text)


def test_all_eight_commands_are_documented() -> None:
    readme = readme_text()
    command_lines = [
        "srcwhere check MAP",
        "srcwhere decode MAP [--line N]",
        "srcwhere lookup MAP LINE:COL",
        "srcwhere reverse MAP SOURCE LINE:COL",
        "srcwhere symbolize MAP TRACE [--file NAME]",
        "srcwhere stats MAP",
        "srcwhere vlq-encode NUMBER...",
        "srcwhere vlq-decode TEXT",
    ]
    for command in command_lines:
        assert command in readme


def test_complete_example_inputs_are_present() -> None:
    readme = readme_text()
    map_text = (
        '{"version":3,"file":"app.min.js","sources":["src/util.ts","src/main.ts"],'
        '"names":["clamp","start"],"sourcesContent":["export function clamp(n: number): number {\\n'
        '  return n < 0 ? 0 : n;\\n}\\n","import { clamp } from \\"./util\\";\\n\\n'
        'export function start(): number {\\n  return clamp(-5);\\n}\\n"],'
        '"mappings":"AAAgBA,cACd,OAAO;ACCOC,cACd,OAAOD;A,GAAP"}'
    )
    trace_text = (
        "Error: boom\n"
        "    at a (https://example.com/static/app.min.js:1:16)\n"
        "    at s (https://example.com/static/app.min.js:2:23)\n"
        "    at https://example.com/static/app.min.js:3:1\n"
        "    at Object.run (https://example.com/static/vendor.js:10:5)\n"
        "start@https://example.com/static/app.min.js:2:15"
    )
    assert_fenced_block(readme, "json", map_text)
    assert_fenced_block(readme, "text", trace_text)


def test_decode_line_example_keeps_its_exact_output_spacing() -> None:
    readme = readme_text()
    output = (
        "line  col  source         oline  ocol  name\n"
        '2     1    "src/main.ts"  3      17    "start"\n'
        '2     15   "src/main.ts"  4      3     -\n'
        '2     22   "src/main.ts"  4      10    "clamp"\n'
        "segments    3"
    )
    assert "srcwhere decode app.js.map --line 2" in readme
    assert_fenced_block(readme, "text", output)


def test_lookup_example_keeps_its_exact_output_spacing() -> None:
    readme = readme_text()
    output = (
        "generated   2:30\n"
        "segment     2:22\n"
        'source      "src/main.ts"\n'
        "original    4:10\n"
        'name        "clamp"\n'
        'text        "  return clamp(-5);"'
    )
    assert "srcwhere lookup app.js.map 2:30" in readme
    assert_fenced_block(readme, "text", output)


def test_symbolize_example_and_negative_exit_are_documented() -> None:
    readme = readme_text()
    output = (
        "Error: boom\n"
        "    at a (src/util.ts:2:3)\n"
        "    at clamp (src/main.ts:4:10)\n"
        "    at https://example.com/static/app.min.js:3:1\n"
        "    at Object.run (https://example.com/static/vendor.js:10:5)\n"
        "start@src/main.ts:4:3"
    )
    assert "srcwhere symbolize app.js.map trace.txt" in readme
    assert_fenced_block(readme, "text", output)
    assert "This symbolize example exits with code 1" in readme


def test_layout_lists_each_explicit_path_once_and_paths_exist() -> None:
    readme = readme_text()
    layout = readme.split("## Layout\n", maxsplit=1)[1]
    actual_paths = [
        line.split("`", maxsplit=2)[1]
        for line in layout.splitlines()
        if line.startswith("- `") and line.count("`") >= 2
    ]
    expected_paths = [path for group_paths in LAYOUT_GROUPS.values() for path in group_paths]

    assert len(actual_paths) == len(set(actual_paths))
    assert actual_paths == expected_paths

    for relative_path in actual_paths:
        path = ROOT.joinpath(*relative_path.rstrip("/").split("/"))
        if relative_path.endswith("/"):
            assert path.is_dir(), relative_path
        else:
            assert path.is_file(), relative_path
