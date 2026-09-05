"""Entry points behind the Makefile. Integrator-owned.

This is the only module allowed to read the system clock (D18). Everything
else takes ``as_of`` or a caller-supplied timestamp as an argument, and a
verify-time test enforces it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leakproof.gates import Gate

#: Commands whose lane has not merged yet, with the issue that tracks it.
NOT_BUILT: dict[str, tuple[str, int]] = {
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
    from leakproof.audit import audit_chain_gate
    from leakproof.gates import BASE_GATES
    from leakproof.ratecard.gate import config_error_gate

    return [
        *BASE_GATES,
        config_error_gate,
        lambda: audit_chain_gate(Path("out/audit.jsonl"), Path("out/claims")),
    ]


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


def _demo_report():
    """Generate then parse the canonical keyless demo batch."""
    from leakproof.generator.manifest import load_manifest
    from leakproof.generator.presets import generate_preset, preset_dir
    from leakproof.ingest import (
        load_profile,
        parse_bank,
        parse_evidence,
        parse_orders,
        parse_settlement_file,
    )
    from leakproof.ratecard import load_rate_card
    from leakproof.triage import run_batch
    from leakproof.types import BatchInputs

    root = Path("out/batches")
    manifests = generate_preset("demo", root)
    manifest = manifests[0]
    directory = preset_dir(root, "demo", manifest.seed)
    # Round-trip the manifest so the CLI uses exactly the persisted batch.
    manifest = load_manifest(directory / "manifest.json")
    files = manifest.files
    settlements = tuple(
        parse_settlement_file(path) for path in sorted(directory.glob("settlement_*.txt"))
    )
    inputs = BatchInputs(
        manifest.batch_id,
        "amazon.in",
        manifest.as_of,
        manifest.cycle_days,
        manifest.coverage,
        parse_orders(directory / files["orders"]),
        settlements,
        load_profile(directory / files["seller_profile"]),
        parse_bank(directory / files["bank"]),
        parse_evidence(directory / files["evidence"]),
    )
    report = run_batch(inputs, load_rate_card())
    drafts_dir = Path("tests/fixtures/drafts")
    if drafts_dir.exists():
        from leakproof.triage import apply_drafts
        from leakproof.types import Draft

        draft_objs = {}
        for p in sorted(drafts_dir.glob("*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            draft_objs[data["finding_id"]] = Draft(
                finding_id=data["finding_id"],
                template_text=data["template_text"],
                rendered_text=data["rendered_text"],
                magnitude=data["magnitude"],
                model=data["model"],
                model_version=data["model_version"],
                placeholders=tuple(data["placeholders"]),
            )
        report = apply_drafts(report, draft_objs)
    return report, manifest


def cmd_demo(_: argparse.Namespace) -> int:
    from leakproof.dashboard import write_demo_html
    from leakproof.serialize import dumps

    report, _ = _demo_report()
    Path("out").mkdir(exist_ok=True)
    Path("out/report.json").write_text(dumps(report), encoding="utf-8")
    write_demo_html(report, Path("out/demo.html"))
    print("wrote out/demo.html")
    return 0


def cmd_metrics(_: argparse.Namespace) -> int:
    from leakproof.labels import load_labels
    from leakproof.metrics import score

    report, manifest = _demo_report()
    print(json.dumps(score(report, manifest, load_labels()), indent=2))
    return 0


def cmd_triage(_: argparse.Namespace) -> int:
    from leakproof.draft import run_triage_job

    report, _ = _demo_report()
    run_triage_job(report, Path("out/drafts"), model="claude-sonnet-5")
    print("draft artifacts written to out/drafts")
    return 0


def cmd_serve(_: argparse.Namespace) -> int:
    from leakproof.dashboard.serve import create_app

    try:
        import uvicorn
    except ImportError as exc:
        raise ImportError("install the serve extra to run leakproof serve") from exc
    report_path = Path("out/report.json")
    if not report_path.exists():
        cmd_demo(argparse.Namespace())
    print("\n" + "=" * 60)
    print("  🚀 LeakProof Live Finance Controller Running!")
    print("  👉 Open in your browser: http://127.0.0.1:8000")
    print("  🟢 Interactive Approve, Override, Reject & Flag active")
    print("=" * 60 + "\n")
    uvicorn.run(create_app(report_path, clock=now_iso), host="127.0.0.1", port=8000)
    return 0


def main(argv: list[str] | None = None) -> int:
    from leakproof.generator import command as gen_command

    parser = argparse.ArgumentParser(prog="leakproof", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify", help="run every hard gate; zero network, no key")
    gen_command.add_arguments(sub.add_parser("gen", help="write a synthetic batch"))
    for name in (*NOT_BUILT, "demo", "serve", "triage", "metrics"):
        sub.add_parser(name)
    args = parser.parse_args(argv)
    if args.cmd == "verify":
        return cmd_verify(args)
    if args.cmd == "gen":
        return gen_command.run(args)
    if args.cmd == "demo":
        return cmd_demo(args)
    if args.cmd == "metrics":
        return cmd_metrics(args)
    if args.cmd == "triage":
        return cmd_triage(args)
    if args.cmd == "serve":
        return cmd_serve(args)
    return cmd_not_built(args.cmd)
