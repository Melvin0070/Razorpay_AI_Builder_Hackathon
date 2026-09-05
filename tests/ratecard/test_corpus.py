"""Corpus hygiene: every rule dated, cited and integer-valued (D17, D14, D3)."""

import json
from datetime import date

from leakproof.contract import CATEGORY_NODES, LineKind
from leakproof.ratecard import load_rate_card
from tests.ratecard.conftest import CORPUS


def test_every_rule_carries_a_citation_with_a_url_and_an_as_of_date(card):
    for rule in card.rules:
        c = rule.citation
        assert c.url.startswith("https://"), rule.rule_id
        assert isinstance(c.as_of, date), rule.rule_id
        assert c.label.strip(), rule.rule_id
        assert isinstance(c.verified, bool), rule.rule_id


#: Rules whose rate is derived from a read source rather than read off one. The
#: TCS aggregate is the CGST leg doubled, and the settlement file withholds the
#: aggregate; no page states that figure, so no page for it was read.
DERIVED_RATES = {"cgst-52-2018-tcs-aggregate", "cgst-15-2024-tcs-aggregate"}


def test_a_derived_rate_is_never_marked_verified(card):
    """D14: verified is true only where the primary page for THAT number was
    read. A derived figure has no such page, however solid the arithmetic."""
    for rule_id in sorted(DERIVED_RATES):
        rule = next(r for r in card.rules if r.rule_id == rule_id)
        assert rule.citation.verified is False, rule_id


def test_a_citation_that_says_something_was_not_read_is_not_verified(corpus_documents):
    """The standard, not two rule ids: a label admitting an unread source and a
    verified:true flag beside it is the pair D14 exists to prevent."""
    for name, doc in corpus_documents.items():
        for raw in doc.get("rules", ()):
            citation = raw.get("citation")
            if citation and "not read" in citation["label"]:
                assert citation["verified"] is False, f"{name}:{raw['rule_id']}"


def test_rule_ids_are_unique(card):
    ids = [r.rule_id for r in card.rules]
    assert len(ids) == len(set(ids))


def test_money_and_basis_points_are_integers(card):
    for rule in card.rules:
        for value in (
            rule.percent_bp,
            rule.fixed_paise,
            rule.slab_min_paise,
            rule.slab_max_paise,
        ):
            assert value is None or (isinstance(value, int) and not isinstance(value, bool))


def test_no_float_anywhere_in_the_corpus_files():
    """A rate written as 12.5 would silently become a float on the money path."""

    def walk(node, where):
        if isinstance(node, float):
            raise AssertionError(f"float in corpus at {where}: {node!r}")
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{where}[{i}]")

    for path in sorted(CORPUS.glob("*.json")):
        walk(json.loads(path.read_text(encoding="utf-8")), path.name)


def test_every_audited_rule_prices_something_and_every_acknowledgement_does_not(card):
    for rule in card.rules:
        priced = rule.percent_bp is not None or rule.fixed_paise is not None
        assert priced is rule.audited, rule.rule_id


def test_validity_windows_are_ordered(card):
    for rule in card.rules:
        assert rule.valid_to is None or rule.valid_from <= rule.valid_to, rule.rule_id


def test_declared_categories_are_the_pinned_contract_nodes(card):
    assert set(card.coverage().categories) == set(CATEGORY_NODES)


def test_each_category_rule_names_the_fee_category_node_it_was_read_from(corpus_documents):
    """RS3 section 1: an unpinned identifier would make the declaration false."""
    nodes = corpus_documents["coverage.json"]["category_nodes"]
    for name, doc in corpus_documents.items():
        for raw in doc.get("rules", ()):
            if raw.get("category_id") is None:
                continue
            node = raw.get("category_node")
            assert node, f"{name}:{raw['rule_id']} has no category_node"
            assert node == nodes[raw["category_id"]], f"{name}:{raw['rule_id']} node {node!r}"


def test_every_divergence_from_the_contract_pin_is_declared_with_a_reason(corpus_documents):
    """The corpus may encode a node under a different name than contract.py
    pins, but only out loud: a silent rename would make the coverage
    declaration false in exactly the way D17 exists to prevent."""
    coverage = corpus_documents["coverage.json"]
    nodes = coverage["category_nodes"]
    declared = coverage.get("category_node_divergences", {})
    assert set(nodes) == set(CATEGORY_NODES)
    for category_id, node in nodes.items():
        if node == CATEGORY_NODES[category_id]:
            assert category_id not in declared, category_id
            continue
        assert declared.get(category_id, "").strip(), (
            f"{category_id} encodes node {node!r} but contract.CATEGORY_NODES pins "
            f"{CATEGORY_NODES[category_id]!r} and no divergence is declared"
        )


def test_technology_fee_has_neither_a_rule_nor_an_acknowledgement(card):
    """C8_CODE_KNOWN_NO_RULE depends on exactly this hole existing."""
    assert all(r.kind is not LineKind.TECHNOLOGY_FEE for r in card.rules)
    coverage = card.coverage()
    assert LineKind.TECHNOLOGY_FEE not in coverage.audited_kinds
    assert LineKind.TECHNOLOGY_FEE not in coverage.acknowledged_kinds


def test_unclassified_is_never_declared(card):
    """C8_CODE_UNSEEN: an unknown code has no corpus entry by construction."""
    assert all(r.kind is not LineKind.UNCLASSIFIED for r in card.rules)


def test_load_rate_card_defaults_to_the_packaged_corpus(card):
    assert load_rate_card(CORPUS).rules == card.rules
