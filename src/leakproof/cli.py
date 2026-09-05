"""Entry points behind the Makefile. Integrator-owned.

This is the only module allowed to read the system clock (D18). Everything
else takes ``as_of`` or a caller-supplied timestamp as an argument, and a
verify-time test enforces it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leakproof.gates import Gate

#: Commands whose lane has not merged yet, with the issue that tracks it.
NOT_BUILT: dict[str, tuple[str, int]] = {
    "demo": ("G", 10),
    "serve": ("G", 10),
    "triage": ("M", 16),
    "metrics": ("N", 17),
    "throughput": ("N", 17),
}


def now_iso() -> str:
    """Wall-clock timestamp for audit entries. Never used for window arithmetic."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def hard_gates() -> list[Gate]:
    """Composition root for the hard gates (D10).

    Lane gates are registered here rather than in ``gates.py`` because that
    module is imported by walled packages, so a lane import there would make
    every walled package reach that lane and fail the D12 wall test. Nothing
    imports ``cli``, so it can see everything (lane C, Wave 1).
    """
    from leakproof.gates import BASE_GATES
    from leakproof.ratecard.gate import config_error_gate

    return [*BASE_GATES, config_error_gate]


def cmd_verify(_: argparse.Namespace) -> int:
    from leakproof.gates import run_hard_gates

    results = run_hard_gates(hard_gates())
    for r in results:
        print(f"[{'ok' if r.ok else 'FAIL'}] {r.name}: {r.detail}")
    failed = [r for r in results if not r.ok]
    print(f"verify: {len(results)} hard gate(s), {len(failed)} failed")
    return 1 if failed else 0


def cmd_not_built(name: str) -> int:
    lane, issue = NOT_BUILT[name]
    print(f"leakproof {name}: not built yet (lane {lane}, issue #{issue})", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    from leakproof.generator import command as gen_command

    parser = argparse.ArgumentParser(prog="leakproof", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify", help="run every hard gate; zero network, no key")
    gen_command.add_arguments(sub.add_parser("gen", help="write a synthetic batch"))
    for name in NOT_BUILT:
        sub.add_parser(name)
    args = parser.parse_args(argv)
    if args.cmd == "verify":
        return cmd_verify(args)
    if args.cmd == "gen":
        return gen_command.run(args)
    return cmd_not_built(args.cmd)
