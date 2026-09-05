"""``leakproof gen``: the argument parser and handler for the CLI's ``gen``
sub-command. ``cli.py`` is integrator-owned, so the lane registers through
this file and the integrator wires ``add_arguments`` / ``run`` at merge
(strategy doc §3)."""

from __future__ import annotations

import argparse
from pathlib import Path

from leakproof.generator.presets import PRESETS, generate_preset, preset_dir

DEFAULT_OUT: Path = Path("out") / "batches"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        default="demo",
        help="which batch to generate; --all generates every preset",
    )
    parser.add_argument("--all", action="store_true", help="generate every preset")
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help="root directory; one folder per preset"
    )


def run(args: argparse.Namespace) -> int:
    names = sorted(PRESETS) if args.all else [args.preset]
    for name in names:
        for manifest in generate_preset(name, args.out):
            directory = preset_dir(args.out, name, manifest.seed)
            seeded = sum(1 for e in manifest.seeded if e.expected_class is not None)
            print(
                f"{name}: {directory} orders={manifest.order_count} seeded_errors={seeded} "
                f"as_of={manifest.as_of.isoformat()} cycles={len(manifest.files) - 4}"
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="leakproof gen", description=__doc__)
    add_arguments(parser)
    return run(parser.parse_args(argv))


if __name__ == "__main__":  # pragma: no cover - until cli.py wires `gen`
    raise SystemExit(main())
