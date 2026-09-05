"""The corpus really implements ``types.RateCard`` (D12).

The claim is made in three docstrings and enforced by nothing: this repo runs no
type checker, so a Protocol is a comment until something calls it. Lanes J and L
are coded against the seam and hold no import of this package, so a rename here
would reach them at runtime and not before.
"""

import inspect
from datetime import date

from leakproof.contract import LineKind
from leakproof.ratecard import load_rate_card
from leakproof.types import CoverageDeclaration, LookupMiss, RateCard, RateRule

INSIDE = date(2026, 8, 21)


def _protocol_methods() -> dict[str, object]:
    return {
        name: member
        for name, member in vars(RateCard).items()
        if callable(member) and not name.startswith("_")
    }


def test_the_protocol_still_has_the_two_methods_the_corpus_answers():
    """A guard on the guard: if the seam grows a third method, the conformance
    test below must be taught about it rather than passing vacuously."""
    assert set(_protocol_methods()) == {"lookup", "coverage"}


def test_the_corpus_implements_every_protocol_method_with_a_compatible_signature(card):
    for name, declared in _protocol_methods().items():
        impl = getattr(type(card), name, None)
        assert callable(impl), f"the corpus does not implement {name}"
        want = [p for p in inspect.signature(declared).parameters.values() if p.name != "self"]
        got = [p for p in inspect.signature(impl).parameters.values() if p.name != "self"]
        assert [p.name for p in got[: len(want)]] == [p.name for p in want], name
        # lookup takes band_key_paise, which the frozen Protocol does not name.
        # Extra parameters are fine; extra REQUIRED ones would break every
        # caller holding the seam.
        for extra in got[len(want) :]:
            assert extra.default is not inspect.Parameter.empty, f"{name}: {extra.name}"


def test_a_caller_holding_only_the_seam_gets_the_declared_return_types():
    seam: RateCard = load_rate_card()

    coverage = seam.coverage()
    assert isinstance(coverage, CoverageDeclaration)
    assert coverage.categories and coverage.audited_kinds

    hit = seam.lookup(LineKind.FEE_TAX, "apparel", INSIDE)
    assert isinstance(hit, RateRule)
    miss = seam.lookup(LineKind.TECHNOLOGY_FEE, "apparel", INSIDE)
    assert isinstance(miss, LookupMiss)
