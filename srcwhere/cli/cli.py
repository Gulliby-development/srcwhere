from srcwhere.base.fail import Fail
from srcwhere.base.inputs import IO
from srcwhere.base.options import parse_options
from srcwhere.base.text import show
from srcwhere.cli import (
    cmd_check,
    cmd_decode,
    cmd_lookup,
    cmd_reverse,
    cmd_stats,
    cmd_symbolize,
    cmd_vlq_decode,
    cmd_vlq_encode,
)

COMMANDS = {
    "check": cmd_check,
    "decode": cmd_decode,
    "lookup": cmd_lookup,
    "reverse": cmd_reverse,
    "symbolize": cmd_symbolize,
    "stats": cmd_stats,
    "vlq-encode": cmd_vlq_encode,
    "vlq-decode": cmd_vlq_decode,
}


def run(argv: list[str], io: IO) -> int:
    """Dispatch one command, writing exactly one complete result to the IO."""
    try:
        if not argv:
            raise Fail(
                "missing command (check, decode, lookup, reverse, symbolize, stats, "
                "vlq-encode or vlq-decode)"
            )

        command = argv[0]
        if command == "--help" and len(argv) == 1:
            help_text = "\n".join(module.USAGE for module in COMMANDS.values()) + "\n"
            io.out(help_text)
            return 0

        module = COMMANDS.get(command)
        if module is None:
            raise Fail(f"unknown command {show(command)}")

        options, arguments = parse_options(argv[1:], module.SPECS)
        if len(arguments) < len(module.ARGS):
            raise Fail(f"missing {module.ARGS[len(arguments)]}")
        if len(arguments) > module.MAX:
            raise Fail("too many arguments")

        command_name = command.replace("-", "_")
        command_runner = getattr(module, f"run_{command_name}")
        output, status = command_runner(arguments, options, io)
        io.out(output)
        return status
    except Fail as error:
        io.err(f"srcwhere: {error}\n")
        return 2
