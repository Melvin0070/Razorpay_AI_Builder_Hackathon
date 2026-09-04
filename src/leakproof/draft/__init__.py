"""LLM drafter, placeholders in and out, resumable artifacts. Lane M · Tier B · issue #16.

Governed by D2, D11, D1. Owns this package. The prompt carries no rupee
amounts; checks (a), (a′), (b) run in verify over committed artifacts with
zero network.
"""

from __future__ import annotations

from pathlib import Path

from leakproof.types import BatchReport, Draft, TriagedFinding


def draft_finding(item: TriagedFinding, *, model: str) -> Draft:
    raise NotImplementedError("lane M, issue #16")


def run_triage_job(report: BatchReport, out_dir: Path, *, model: str, resume: bool = True) -> None:
    raise NotImplementedError("lane M, issue #16")


def check_drafts(report: BatchReport, artifacts_dir: Path) -> list[str]:
    """D2 (a) (a′) (b). Returns violations; empty means the gate passes."""
    raise NotImplementedError("lane M, issue #16")
