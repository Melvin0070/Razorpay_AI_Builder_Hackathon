"""Accuracy harness, both match rates, holdout line, throughput. Lane N · Tier A · issue #17.

Governed by D10, D12 (holdout line), D13, D9. Owns this package. Everything
here is published, never gated, except the throughput threshold (D13).
"""

from __future__ import annotations

from collections import defaultdict

from leakproof.contract import TOLERANCE_PAISE
from leakproof.detect import run_detectors
from leakproof.evidence import assess
from leakproof.ratecard import load_rate_card
from leakproof.scenarios import Scenario
from leakproof.triage import derive_state
from leakproof.types import BatchReport, ClaimabilityLabel, DetectorContext, HoldoutCase, Manifest


def score(
    report: BatchReport, manifest: Manifest, labels: dict[Scenario, ClaimabilityLabel]
) -> dict[str, object]:
    predicted = {(x.finding.order_id, x.finding.error_class): x.finding for x in report.queue}
    truth = [x for x in manifest.seeded if x.expected_class is not None]
    hits = [x for x in truth if (x.order_id, x.expected_class) in predicted]
    by_class: dict[str, dict[str, int]] = defaultdict(lambda: {"expected": 0, "found": 0})
    for seeded in truth:
        bucket = by_class[str(int(seeded.expected_class))]
        bucket["expected"] += 1
        if (seeded.order_id, seeded.expected_class) in predicted:
            bucket["found"] += 1
    disagreements = []
    for seeded in hits:
        actual = predicted[(seeded.order_id, seeded.expected_class)].amount_paise
        expected = seeded.expected_amount_paise
        if expected is not None and abs(actual - expected) > TOLERANCE_PAISE:
            disagreements.append(
                {
                    "order_id": seeded.order_id,
                    "class": int(seeded.expected_class),
                    "expected_paise": expected,
                    "actual_paise": actual,
                }
            )
    state_expected = [x for x in truth if x.scenario in labels]
    states = {q.finding.finding_id: q.state.state for q in report.queue}
    state_hits = sum(
        1
        for x in state_expected
        if (item := predicted.get((x.order_id, x.expected_class))) is not None
        and states.get(item.finding_id) == labels[x.scenario].expected_state
    )
    return {
        "seeded_errors": len(truth),
        "detected_seeded_errors": len(hits),
        "recall": len(hits) / len(truth) if truth else 0.0,
        "precision": len(hits) / len(report.queue) if report.queue else 0.0,
        "per_class_recall": {
            key: value["found"] / value["expected"] if value["expected"] else 0.0
            for key, value in sorted(by_class.items())
        },
        "rupee_agreement": (len(hits) - len(disagreements)) / len(hits) if hits else 0.0,
        "rupee_disagreements": disagreements,
        "claimability_label_agreement": state_hits / len(state_expected)
        if state_expected
        else None,
        "strict_match_rate": report.match_rates.strict,
        "adjusted_match_rate": report.match_rates.adjusted,
    }


def score_holdout(cases: tuple[HoldoutCase, ...]) -> dict[str, object]:
    card = load_rate_card()
    passed = 0
    disagreements = []
    for case in cases:
        findings = run_detectors(
            (case.folded,),
            DetectorContext(
                card,
                case.profile,
                case.folded.as_of,
                7,
                case.batch_max_settlement_date or case.folded.as_of,
            ),
        )
        actual = next((x for x in findings if x.error_class == case.expected_class), None)
        actual_state = (
            derive_state(actual, assess(actual, case.folded, case.profile, case.folded.as_of)).state
            if actual is not None
            else None
        )
        amount_ok = case.expected_amount_paise is None or (
            actual is not None
            and abs(actual.amount_paise - case.expected_amount_paise) <= TOLERANCE_PAISE
        )
        if (
            (actual.error_class if actual else None) == case.expected_class
            and actual_state == case.expected_state
            and amount_ok
        ):
            passed += 1
        else:
            disagreements.append(
                {
                    "case_id": case.case_id,
                    "expected_class": int(case.expected_class) if case.expected_class else None,
                    "actual_class": int(actual.error_class) if actual else None,
                    "expected_state": case.expected_state.value if case.expected_state else None,
                    "actual_state": actual_state.value if actual_state else None,
                }
            )
    return {
        "cases": len(cases),
        "passed": passed,
        "accuracy": passed / len(cases) if cases else 0.0,
        "disagreements": disagreements,
    }
