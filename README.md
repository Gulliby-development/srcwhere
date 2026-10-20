<p align="center"><img src="docs/logo.svg" width="96" alt="" /></p>

# srcwhere

srcwhere is an offline command-line tool for debugging minified or bundled JavaScript with version 3 source maps. It validates maps, decodes generated-to-original mappings, looks up positions in either direction, summarizes map contents, rewrites stack traces, and encodes or decodes base64 VLQ mapping numbers. It is intended for developers diagnosing production JavaScript bundles and the source files they came from.

[![CI](https://github.com/Gulliby-development/srcwhere/actions/workflows/ci.yml/badge.svg)](https://github.com/Gulliby-development/srcwhere/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Why

When a production error points at `app.min.js:1:48213`, you need the original file, line and column, and often the original source text. `srcwhere` answers that from the `.map` file alone, offline, with no dependency beyond Python: validate a map, look up positions in both directions, and rewrite a whole stack trace in one command.

## Install

srcwhere requires Python 3.11 or newer and uses only the Python standard library at runtime. There are no package dependencies and no installed console-script contract. Clone the repository, then run commands from its root:

```sh
git clone https://github.com/Gulliby-development/srcwhere.git
cd srcwhere
```

Check that it runs:

```sh
python -m srcwhere --help
```

The command forms below use the literal `srcwhere ...` notation from the CLI help. From this checkout, invoke any such command as `python -m srcwhere ...`.

## Usage

```text
srcwhere COMMAND ...
```

`MAP` and `TRACE` name files. Use `-` for standard input when an input is piped; `symbolize` reads the map before the trace, and only one of its two inputs may be `-`. User-supplied line and column positions are one-based. Map mapping fields are zero-based internally.

The complete example inputs used below are:

`app.js.map`:

```json
{"version":3,"file":"app.min.js","sources":["src/util.ts","src/main.ts"],"names":["clamp","start"],"sourcesContent":["export function clamp(n: number): number {\n  return n < 0 ? 0 : n;\n}\n","import { clamp } from \"./util\";\n\nexport function start(): number {\n  return clamp(-5);\n}\n"],"mappings":"AAAgBA,cACd,OAAO;ACCOC,cACd,OAAOD;A,GAAP"}
```

`trace.txt`:

```text
Error: boom
    at a (https://example.com/static/app.min.js:1:16)
    at s (https://example.com/static/app.min.js:2:23)
    at https://example.com/static/app.min.js:3:1
    at Object.run (https://example.com/static/vendor.js:10:5)
start@https://example.com/static/app.min.js:2:15
```

## Commands

`srcwhere --help` prints these eight usage lines in this order:

```text
usage: srcwhere check MAP
       srcwhere decode MAP [--line N]
       srcwhere lookup MAP LINE:COL
       srcwhere reverse MAP SOURCE LINE:COL
       srcwhere symbolize MAP TRACE [--file NAME]
       srcwhere stats MAP
       srcwhere vlq-encode NUMBER...
       srcwhere vlq-decode TEXT
```

- `srcwhere check MAP` validates a map and reports all structural or mapping problems.
- `srcwhere decode MAP [--line N]` prints the decoded segments as a table; optional `--line N` selects one generated line (1 through 1,000,000).
- `srcwhere lookup MAP LINE:COL` reports the original source position for a generated position, when mapped.
- `srcwhere reverse MAP SOURCE LINE:COL` finds generated positions for a source position.
- `srcwhere symbolize MAP TRACE [--file NAME]` rewrites matching stack frames. `--file NAME` selects the bundle filename; otherwise the map's `file` name is used.
- `srcwhere stats MAP` prints map totals and segment counts for each source.
- `srcwhere vlq-encode NUMBER...` encodes one to twenty signed VLQ numbers.
- `srcwhere vlq-decode TEXT` decodes a VLQ stream.

Run the following examples from the repository root as `python -m srcwhere` followed by the shown command.

Decode generated line 2:

```text
srcwhere decode app.js.map --line 2
```

```text
line  col  source         oline  ocol  name
2     1    "src/main.ts"  3      17    "start"
2     15   "src/main.ts"  4      3     -
2     22   "src/main.ts"  4      10    "clamp"
segments    3
```

Look up generated position 2:30:

```text
srcwhere lookup app.js.map 2:30
```

```text
generated   2:30
segment     2:22
source      "src/main.ts"
original    4:10
name        "clamp"
text        "  return clamp(-5);"
```

Symbolize the example trace:

```text
srcwhere symbolize app.js.map trace.txt
```

```text
Error: boom
    at a (src/util.ts:2:3)
    at clamp (src/main.ts:4:10)
    at https://example.com/static/app.min.js:3:1
    at Object.run (https://example.com/static/vendor.js:10:5)
start@src/main.ts:4:3
```

This symbolize example exits with code 1 because the matching frame at 3:1 has no source mapping. The vendor frame is for another file and remains unchanged.

## Exit codes

- `0`: the command completed successfully.
- `1`: a negative result, such as map problems from `check`, an unmapped `lookup` or `reverse` position, or an unmapped matching frame from `symbolize`.
- `2`: an input, option, argument, or other command error. Errors are written to standard error and do not write command output to standard output.

## Development

Run checks from the repository root with Python 3.11 or newer. The project checks are:

```sh
python -m pip install pytest ruff
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

The tests use in-memory inputs except for the dedicated malformed-standard-input process test; the documentation tests read this README and check the declared layout paths.

## License

MIT, see [LICENSE](LICENSE).

## Layout

The lists below use the explicit package and test inventory.

### Package root

- `srcwhere/`
- `srcwhere/__init__.py`
- `srcwhere/__main__.py`

### Base layer

- `srcwhere/base/`
- `srcwhere/base/__init__.py`
- `srcwhere/base/fail.py`
- `srcwhere/base/text.py`
- `srcwhere/base/ints.py`
- `srcwhere/base/options.py`
- `srcwhere/base/inputs.py`

### VLQ layer

- `srcwhere/vlq/`
- `srcwhere/vlq/__init__.py`
- `srcwhere/vlq/codec.py`
- `srcwhere/vlq/stream.py`

### Source-map layer

- `srcwhere/smap/`
- `srcwhere/smap/__init__.py`
- `srcwhere/smap/model.py`
- `srcwhere/smap/mappings.py`
- `srcwhere/smap/structure.py`
- `srcwhere/smap/sections.py`
- `srcwhere/smap/loader.py`

### Query layer

- `srcwhere/query/`
- `srcwhere/query/__init__.py`
- `srcwhere/query/lookup.py`
- `srcwhere/query/reverse.py`
- `srcwhere/query/stats.py`

### Trace layer

- `srcwhere/trace/`
- `srcwhere/trace/__init__.py`
- `srcwhere/trace/frames.py`
- `srcwhere/trace/remap.py`

### CLI layer

- `srcwhere/cli/`
- `srcwhere/cli/__init__.py`
- `srcwhere/cli/cmd_check.py`
- `srcwhere/cli/cmd_decode.py`
- `srcwhere/cli/cmd_lookup.py`
- `srcwhere/cli/cmd_reverse.py`
- `srcwhere/cli/cmd_symbolize.py`
- `srcwhere/cli/cmd_stats.py`
- `srcwhere/cli/cmd_vlq_encode.py`
- `srcwhere/cli/cmd_vlq_decode.py`
- `srcwhere/cli/cli.py`

### Tests

- `tests/`
- `tests/test_text.py`
- `tests/test_options.py`
- `tests/test_vlq.py`
- `tests/test_structure.py`
- `tests/test_mappings.py`
- `tests/test_loader.py`
- `tests/test_query.py`
- `tests/test_frames.py`
- `tests/test_remap.py`
- `tests/test_cmd_map.py`
- `tests/test_cmd_find.py`
- `tests/test_cmd_trace.py`
- `tests/test_cli.py`
- `tests/test_process.py`
- `tests/test_docs.py`

---

Built with BAKED
