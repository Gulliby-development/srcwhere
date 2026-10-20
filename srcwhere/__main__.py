import sys

from srcwhere.base.inputs import StdIO
from srcwhere.cli.cli import run

if __name__ == "__main__":
    sys.exit(run(sys.argv[1:], StdIO()))
