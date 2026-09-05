"""Tests for D2 architectural checks (a), (a'), and (b) in leakproof.draft.

Verifies that:
1. Committed draft artifacts in tests/fixtures/drafts pass all D2 checks with zero network.
2. check_drafts reliably catches currency/numeral leaks, uncited placeholders, and amount leaks.
3. _render deterministically resolves placeholders to formatted rupee values.
"""

from __future__ import annotations

import json
from pathlib import Path

from leakproof.cli import _demo_report
from leakproof.draft import _render, check_drafts


def test_committed_drafts_pass_all_d2_checks():
    report, _ = _demo_report()
    drafts_dir = Path(__file__).resolve().parents[1] / "fixtures" / "drafts"
    assert drafts_dir.exists(), "tests/fixtures/drafts must exist"
    violations = check_drafts(report, drafts_dir)
    assert violations == [], f"D2 violations found: {violations}"


def test_check_drafts_detects_currency_or_numeric_amount(tmp_path):
    report, _ = _demo_report()
    item = report.queue[0]
    line = item.finding.source_line_ids[0]
    bad_artifact = {
        "finding_id": item.finding.finding_id,
        "template_text": f"Requesting refund of ₹500 for {{{{amt:{line}}}}}.",
        "rendered_text": "Requesting refund of ₹500 for ₹2,798.88.",
        "magnitude": "moderate",
        "model": "claude-sonnet-5",
        "model_version": "2026-06-01",
        "placeholders": [line],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad_artifact), encoding="utf-8")
    violations = check_drafts(report, tmp_path)
    assert any("currency or numeric amount" in v for v in violations)


def test_check_drafts_detects_uncited_placeholder(tmp_path):
    report, _ = _demo_report()
    item = report.queue[0]
    bad_artifact = {
        "finding_id": item.finding.finding_id,
        "template_text": "Dispute on {{amt:uncited_settlement.txt:999}}.",
        "rendered_text": "Dispute on ₹100.00.",
        "magnitude": "moderate",
        "model": "claude-sonnet-5",
        "model_version": "2026-06-01",
        "placeholders": ["uncited_settlement.txt:999"],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad_artifact), encoding="utf-8")
    violations = check_drafts(report, tmp_path)
    assert any("uncited placeholder" in v for v in violations)


def test_check_drafts_detects_amount_leak(tmp_path):
    report, _ = _demo_report()
    item = report.queue[0]
    line = item.finding.source_line_ids[0]
    amount_rupees = item.finding.amount_paise / 100.0
    bad_artifact = {
        "finding_id": item.finding.finding_id,
        "template_text": f"Discrepancy of {amount_rupees:.2f} detected on {{{{amt:{line}}}}}.",
        "rendered_text": f"Discrepancy of {amount_rupees:.2f} detected on ₹{amount_rupees:.2f}.",
        "magnitude": "moderate",
        "model": "claude-sonnet-5",
        "model_version": "2026-06-01",
        "placeholders": [line],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad_artifact), encoding="utf-8")
    violations = check_drafts(report, tmp_path)
    assert len(violations) > 0


def test_render_resolves_placeholders_to_exact_paise():
    report, _ = _demo_report()
    item = next(
        x
        for x in report.queue
        if x.finding.finding_id == "408-9606110-9190751|1|settlement_2026-08-07.txt:189"
    )
    tmpl = (
        "Commission was charged in excess. Recomputation attached; requesting adjustment of "
        "{{amt:settlement_2026-08-07.txt:189}} to the referral fee."
    )
    rendered = _render(tmpl, item)
    assert "₹399.92" in rendered
