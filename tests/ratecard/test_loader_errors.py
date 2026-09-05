"""A malformed corpus must fail loudly at load, not quietly at lookup.

CorpusError is distinct from CONFIG_ERROR on purpose: CONFIG_ERROR is a
well-formed corpus that cannot answer a question inside its own coverage, which
is a rate-card bug the gate reports. These are files that are not a corpus at
all, which is a build that cannot start.
"""

import json

import pytest

from leakproof.ratecard import CorpusError, load_corpus, load_rate_card

COVERAGE = {
    "categories": ["apparel"],
    "valid_from": "2026-03-16",
    "valid_to": None,
    "audited_kinds": ["fee-tax"],
    "acknowledged_kinds": [],
}
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


#: A banded rule and the coverage block that must accompany one.
BANDED = {
    **RULE,
    "rule_id": "b1",
    "kind": "commission",
    "category_id": "apparel",
    "percent_bp": 2100,
    "slab_basis": "unit-item-price",
    "slab_min_paise": 100001,
}
#: The same coverage block with and without the slab_bases a banded rule needs.
BANDED_KINDS = {**COVERAGE, "audited_kinds": ["commission"]}
BANDED_COVERAGE = {**BANDED_KINDS, "slab_bases": {"commission": "unit-item-price"}}


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


@pytest.mark.parametrize("percent_bp", [-1800, -1, 10_001])
def test_a_rate_outside_zero_to_a_hundred_percent_is_rejected(tmp_path, percent_bp):
    """percent_bp -1800 used to load clean and price an 18% credit."""
    rule = {**RULE, "percent_bp": percent_bp}
    root = _write(tmp_path / "c", docs={"rules.json": {"source": SOURCE, "rules": [rule]}})
    with pytest.raises(CorpusError, match=r"outside 0\.\.10000 basis points"):
        load_rate_card(root)


@pytest.mark.parametrize("percent_bp", [0, 10_000])
def test_the_ends_of_the_basis_point_range_are_accepted(tmp_path, percent_bp):
    """Apparel really does price a 0% band, so the bound is inclusive."""
    rule = {**RULE, "percent_bp": percent_bp}
    root = _write(tmp_path / "c", docs={"rules.json": {"source": SOURCE, "rules": [rule]}})
    assert load_corpus(root).rules[0].percent_bp == percent_bp


def test_a_negative_fixed_amount_is_rejected(tmp_path):
    rule = {**RULE, "percent_bp": None, "fixed_paise": -5200}
    root = _write(tmp_path / "c", docs={"rules.json": {"source": SOURCE, "rules": [rule]}})
    with pytest.raises(CorpusError, match="fixed_paise -5200 is negative"):
        load_rate_card(root)


@pytest.mark.parametrize("field", ["slab_min_paise", "slab_max_paise"])
def test_a_negative_slab_bound_is_rejected(tmp_path, field):
    """The gate probes band keys from zero up, so a negative bound is a band
    nothing ever sweeps."""
    rule = {**BANDED, "slab_min_paise": None, field: -1}
    root = _write(
        tmp_path / "c",
        coverage=BANDED_COVERAGE,
        docs={"r.json": {"source": SOURCE, "rules": [rule]}},
    )
    with pytest.raises(CorpusError, match=f"{field} -1 is negative"):
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


def test_a_banded_rule_without_a_slab_basis_is_rejected(tmp_path):
    """The bound alone does not say what figure it is read on, and the two
    banded kinds are read on two different ones."""
    rule = {k: v for k, v in BANDED.items() if k != "slab_basis"}
    root = _write(
        tmp_path / "c",
        coverage=BANDED_COVERAGE,
        docs={"r.json": {"source": SOURCE, "rules": [rule]}},
    )
    with pytest.raises(CorpusError, match="must name the slab_basis"):
        load_rate_card(root)


def test_an_unknown_slab_basis_is_rejected(tmp_path):
    rule = {**BANDED, "slab_basis": "order-principal"}
    root = _write(
        tmp_path / "c",
        coverage=BANDED_COVERAGE,
        docs={"r.json": {"source": SOURCE, "rules": [rule]}},
    )
    with pytest.raises(CorpusError, match="not a slab basis"):
        load_rate_card(root)


def test_a_slab_basis_on_an_unbanded_rule_is_rejected(tmp_path):
    """It would imply a band that does not exist: fee GST rides on the fee."""
    rule = {**RULE, "slab_basis": "unit-item-price"}
    root = _write(tmp_path / "c", docs={"r.json": {"source": SOURCE, "rules": [rule]}})
    with pytest.raises(CorpusError, match="no slab bounds"):
        load_rate_card(root)


def test_one_kind_banded_on_two_different_figures_is_rejected(tmp_path):
    rules = [
        BANDED,
        {**BANDED, "rule_id": "b2", "slab_basis": "buyer-paid-item-price", "slab_min_paise": 1},
    ]
    root = _write(
        tmp_path / "c",
        coverage=BANDED_COVERAGE,
        docs={"r.json": {"source": SOURCE, "rules": rules}},
    )
    with pytest.raises(CorpusError, match="one kind is read on one figure"):
        load_rate_card(root)


def test_banded_rules_with_no_declared_basis_in_coverage_are_rejected(tmp_path):
    root = _write(
        tmp_path / "c",
        coverage=BANDED_KINDS,
        docs={"r.json": {"source": SOURCE, "rules": [BANDED]}},
    )
    with pytest.raises(CorpusError, match="'slab_bases' is required"):
        load_rate_card(root)


def test_a_coverage_declaration_that_contradicts_the_rules_is_rejected(tmp_path):
    """Two statements of one fact only help when they are checked against each
    other; otherwise the dashboard can show a basis the rules do not use."""
    coverage = {**BANDED_KINDS, "slab_bases": {"commission": "buyer-paid-item-price"}}
    root = _write(
        tmp_path / "c",
        coverage=coverage,
        docs={"r.json": {"source": SOURCE, "rules": [BANDED]}},
    )
    with pytest.raises(CorpusError, match="slab_bases declares"):
        load_rate_card(root)


def test_a_declared_kind_no_rule_carries_is_rejected(tmp_path):
    """The kinds are declared, not derived, so a deleted rule document leaves
    its claim standing and fails at load instead of shrinking the sweep."""
    coverage = {**COVERAGE, "audited_kinds": ["fee-tax", "tcs"]}
    root = _write(tmp_path / "c", coverage=coverage)
    with pytest.raises(CorpusError, match=r"declares audited kind\(s\) no rule carries: tcs"):
        load_rate_card(root)


def test_a_rule_of_an_undeclared_kind_is_rejected(tmp_path):
    """The other direction: a kind the corpus prices but never claims resolves
    at lookup and is swept by nothing."""
    rules = [RULE, {**RULE, "rule_id": "r2", "kind": "tcs", "percent_bp": 50}]
    root = _write(tmp_path / "c", docs={"rules.json": {"source": SOURCE, "rules": rules}})
    with pytest.raises(CorpusError, match=r"rules carry audited kind\(s\).*: tcs"):
        load_rate_card(root)


def test_a_coverage_block_without_the_kind_lists_is_rejected(tmp_path):
    coverage = {k: v for k, v in COVERAGE.items() if k != "acknowledged_kinds"}
    root = _write(tmp_path / "c", coverage=coverage)
    with pytest.raises(CorpusError, match="'acknowledged_kinds' is required"):
        load_rate_card(root)


def test_a_declared_kind_that_is_not_a_line_kind_is_rejected(tmp_path):
    coverage = {**COVERAGE, "audited_kinds": ["fee-tax", "referral-fee"]}
    root = _write(tmp_path / "c", coverage=coverage)
    with pytest.raises(CorpusError, match="'referral-fee' is not a LineKind"):
        load_rate_card(root)


def test_a_kind_declared_in_both_lists_is_rejected(tmp_path):
    coverage = {**COVERAGE, "acknowledged_kinds": ["fee-tax"]}
    root = _write(tmp_path / "c", coverage=coverage)
    with pytest.raises(CorpusError, match="either audited or acknowledged"):
        load_rate_card(root)
