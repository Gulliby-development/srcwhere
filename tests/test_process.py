import subprocess
import sys
from pathlib import Path


def test_module_entry_reports_malformed_stdin_bytes() -> None:
    # The guarded module entry constructs StdIO, exercising its real binary stdin path.
    repository_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "srcwhere", "check", "-"],
        check=False,
        cwd=repository_root,
        input=b"AB\xff\n",
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == b"srcwhere: <stdin>: input is not valid UTF-8\n"
