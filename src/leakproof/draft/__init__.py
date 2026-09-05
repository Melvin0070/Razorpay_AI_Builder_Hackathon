"""LLM drafter, placeholders in and out, resumable artifacts. Lane M · Tier B · issue #16.

Governed by D2, D11, D1. Owns this package. The prompt carries no rupee
amounts; checks (a), (a′), (b) run in verify over committed artifacts with
zero network.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from leakproof.contract import State
from leakproof.types import BatchReport, Draft, TriagedFinding

_TOKEN = re.compile(r"\{\{amt:([^}]+)\}\}")


def _magnitude(amount: int) -> str:
    if amount < 50_000:
        return "minor"
    if amount <= 500_000:
        return "moderate"
    return "major"


def _line_amounts(item: TriagedFinding) -> dict[str, int]:
    """Only source rows cited by this finding may be substituted."""
    amounts: dict[str, int] = {}
    # A finding normally cites settlement rows.  An absence finding cites the
    # order row, for which no settlement amount exists; its token is omitted.
    for line in item.assessment.evidence:
        for line_id in line.source_line_ids:
            amounts.setdefault(line_id, item.finding.amount_paise)
    return amounts


def _render(template: str, item: TriagedFinding) -> str:
    allowed = set(item.finding.source_line_ids)
    amounts = _line_amounts(item)

    def replace(match: re.Match[str]) -> str:
        line_id = match.group(1)
        if line_id not in allowed:
            raise ValueError(f"draft placeholder is not cited by finding: {line_id!r}")
        # The discrepancy is the deterministic amount.  This deliberately
        # avoids allowing model output to select an arbitrary source amount.
        paise = amounts.get(line_id, item.finding.amount_paise)
        rupees, remainder = divmod(abs(paise), 100)
        rendered = f"₹{rupees:,}.{remainder:02d}"
        return f"-{rendered}" if paise < 0 else rendered

    return _TOKEN.sub(replace, template)


def _prompt(item: TriagedFinding) -> str:
    tokens = " ".join(f"{{{{amt:{line_id}}}}}" for line_id in item.finding.source_line_ids)
    evidence = "; ".join(f"{e.requirement}: {e.status.value}" for e in item.assessment.evidence)
    deadline = item.assessment.deadline.days_left
    return (
        "Write a concise professional marketplace claim. Do not use numerals, currency symbols, "
        "or amounts; retain the provided placeholders exactly. "
        f"Mechanism: {item.finding.mechanism.value}. Magnitude: {_magnitude(item.finding.amount_paise)}. "
        f"Reason: {item.finding.basis}. Evidence: {evidence or 'none'}. "
        f"Deadline status: {item.assessment.deadline.status.value}; days left: "
        f"{'available' if deadline is not None else 'not applicable'}. Amount placeholders: {tokens}."
    )


def draft_finding(item: TriagedFinding, *, model: str) -> Draft:
    if item.state.state not in (State.CLAIM_READY, State.BLOCKED):
        raise ValueError("only claim-ready or blocked findings can be drafted")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is required for live drafting")
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError("install the triage extra to use live drafting") from exc
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=model, max_tokens=500, messages=[{"role": "user", "content": _prompt(item)}]
    )
    template = "".join(block.text for block in response.content if hasattr(block, "text")).strip()
    if not template:
        raise RuntimeError("draft provider returned no text")
    if re.search(r"₹|\d", template):
        raise ValueError("draft provider returned prohibited numeral or currency text")
    placeholders = tuple(_TOKEN.findall(template))
    return Draft(
        item.finding.finding_id,
        template,
        _render(template, item),
        _magnitude(item.finding.amount_paise),
        model,
        getattr(response, "model", model),
        placeholders,
    )


def run_triage_job(report: BatchReport, out_dir: Path, *, model: str, resume: bool = True) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for item in report.queue:
        if item.state.state not in (State.CLAIM_READY, State.BLOCKED):
            continue
        path = out_dir / f"{item.finding.finding_id.replace('|', '__')}.json"
        if resume and path.exists():
            continue
        draft = draft_finding(item, model=model)
        path.write_text(
            json.dumps(
                {
                    "finding_id": draft.finding_id,
                    "template_text": draft.template_text,
                    "rendered_text": draft.rendered_text,
                    "magnitude": draft.magnitude,
                    "model": draft.model,
                    "model_version": draft.model_version,
                    "placeholders": list(draft.placeholders),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def check_drafts(report: BatchReport, artifacts_dir: Path) -> list[str]:
    """D2 (a) (a′) (b). Returns violations; empty means the gate passes."""
    findings = {x.finding.finding_id: x for x in report.queue}
    violations: list[str] = []
    if not artifacts_dir.exists():
        return violations
    for path in sorted(artifacts_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            item = findings[raw["finding_id"]]
            template = raw["template_text"]
        except (KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
            violations.append(f"{path}: unreadable artifact ({exc})")
            continue
        stripped = _TOKEN.sub("", template)
        if re.search(r"₹|\b\d{3,}\b|\b\d{1,3}(?:,\d{3})+\b", stripped):
            violations.append(f"{path}: template contains currency or numeric amount")
        allowed = set(item.finding.source_line_ids)
        for token in _TOKEN.findall(template):
            if token not in allowed:
                violations.append(f"{path}: uncited placeholder {token!r}")
        # A plain token equal to a source amount is also forbidden, even if it
        # escaped the broader three-digit check.
        for number in re.findall(r"\b\d+(?:\.\d+)?\b", stripped):
            whole, dot, fraction = number.partition(".")
            value = int(whole) * 100 + int((fraction + "00")[:2]) if dot else int(whole) * 100
            if abs(value - item.finding.amount_paise) <= 100:
                violations.append(f"{path}: template leaks finding amount")
    return violations
