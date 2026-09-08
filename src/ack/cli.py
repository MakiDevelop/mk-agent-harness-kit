"""Unified ``ack`` command-line entry point."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from . import guard, hooks, loop, portability_lint, review, settings

Command = Callable[[list[str] | None], int]
COMMANDS: dict[str, Command] = {
    "settings": settings.main,
    "loop": loop.main,
    "review": review.main,
    "hooks": hooks.main,
    "portability-lint": portability_lint.main,
    "guard": guard.main,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ack", description="mk-agent-harness-kit")
    parser.add_argument("command", choices=COMMANDS, help="ACK subcommand")
    return parser


def main(argv: list[str] | None = None) -> int:
    args, remainder = build_parser().parse_known_args(argv)
    return COMMANDS[args.command](remainder)


if __name__ == "__main__":
    raise SystemExit(main())
