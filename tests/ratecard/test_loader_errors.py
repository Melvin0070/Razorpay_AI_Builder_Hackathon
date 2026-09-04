"""A malformed corpus must fail loudly at load, not quietly at lookup.

CorpusError is distinct from CONFIG_ERROR on purpose: CONFIG_ERROR is a
well-formed corpus that cannot answer a question inside its own coverage, which
is a rate-card bug the gate reports. These are files that are not a corpus at
all, which is a build that cannot start.
"""

import json

import pytest

from leakproof.ratecard import CorpusError, load_rate_card

COVERAGE = {"categories": ["apparel"], "valid_from": "2026-03-16", "valid_to": None}
SOURCE = {
    "label": "fixture",
    "url": "https://sell.amazon.in/fees-and-pricing",
    "as_of": "2026-09-04",
    "verified": False,
}
RULE = {
    "rule_id": "r1",
    "kind": "fee-tax",
    "category_id": None,
    "percent_bp": 1800,
    "fixed_paise": None,
    "slab_min_paise": None,
    "slab_max_paise": None,
    "valid_from": "2026-03-16",
    "valid_to": None,
    "audited": True,
}


def _write(root, coverage=COVERAGE, docs=None):
    root.mkdir(parents=True, exist_ok=True)
    (root / "coverage.json").write_text(json.dumps(coverage), encoding="utf-8")
    for name, doc in (docs or {"rules.json": {"source": SOURCE, "rules": [RULE]}}).items():
        (root / name).write_text(json.dumps(doc), encoding="utf-8")
    return root


def test_a_missing_directory_is_a_corpus_error(tmp_path):
    with pytest.raises(CorpusError, match="not found"):
        load_rate_card(tmp_path / "nowhere")


def test_a_rule_document_without_a_source_citation_is_rejected(tmp_path):
    root = _write(tmp_path / "c", docs={"rules.json": {"rules": [RULE]}})
    with pytest.raises(CorpusError, match="source"):
        load_rate_card(root)


def test_a_float_rate_is_rejected_rather_than_coerced(tmp_path):
    """D3: a rate written as 18.0 would put a float on the money path."""
    rule = {**RULE, "percent_bp": 18.0}
    root = _write(tmp_path / "c", docs={"rules.json": {"source": SOURCE, "rules": [rule]}})
    with pytest.raises(CorpusError, match="expected an integer"):
        load_rate_card(root)


def test_a_citation_without_a_url_is_rejected(tmp_path):
    source = {**SOURCE, "url": "the fee schedule"}
    root = _write(tmp_path / "c", docs={"rules.json": {"source": source, "rules": [RULE]}})
    with pytest.raises(CorpusError, match="must be a URL"):
        load_rate_card(root)


def test_an_audited_rule_with_no_rate_is_rejected(tmp_path):
    rule = {**RULE, "percent_bp": None}
    root = _write(tmp_path / "c", docs={"rules.json": {"source": SOURCE, "rules": [rule]}})
    with pytest.raises(CorpusError, match="must carry percent_bp or fixed_paise"):
        load_rate_card(root)


def test_an_acknowledgement_carrying_a_rate_is_rejected(tmp_path):
    """ADR-0005: acknowledged means known and NOT audited, so it prices nothing."""
    rule = {**RULE, "audited": False}
    root = _write(tmp_path / "c", docs={"rules.json": {"source": SOURCE, "rules": [rule]}})
    with pytest.raises(CorpusError, match="must carry no rate"):
        load_rate_card(root)


def test_a_kind_that_is_both_audited_and_acknowledged_is_rejected(tmp_path):
    both = [RULE, {**RULE, "rule_id": "r2", "audited": False, "percent_bp": None}]
    root = _write(tmp_path / "c", docs={"rules.json": {"source": SOURCE, "rules": both}})
    with pytest.raises(CorpusError, match="either audited or acknowledged"):
        load_rate_card(root)


def test_a_duplicate_rule_id_is_rejected(tmp_path):
    docs = {
        "a.json": {"source": SOURCE, "rules": [RULE]},
        "b.json": {"source": SOURCE, "rules": [RULE]},
    }
    root = _write(tmp_path / "c", docs=docs)
    with pytest.raises(CorpusError, match="duplicate rule_id"):
        load_rate_card(root)


def test_a_backwards_validity_window_is_rejected(tmp_path):
    rule = {**RULE, "valid_to": "2026-01-01"}
    root = _write(tmp_path / "c", docs={"rules.json": {"source": SOURCE, "rules": [rule]}})
    with pytest.raises(CorpusError, match="precedes valid_from"):
        load_rate_card(root)


def test_a_corpus_with_no_rules_is_rejected(tmp_path):
    root = _write(tmp_path / "c", docs={"rules.json": {"source": SOURCE, "rules": []}})
    with pytest.raises(CorpusError, match="no rules"):
        load_rate_card(root)
