import json

import pytest

from leakproof.ratecard import RateCardCorpus, load_corpus
from tests.conftest import FIXTURES, SRC

CORPUS = SRC / "ratecard" / "corpus"

#: The deliberately broken corpus behind Scenario.CONFIG_ERROR.
SLAB_GAP_CORPUS = FIXTURES / "ratecard_slab_gap"


@pytest.fixture(scope="session")
def card() -> RateCardCorpus:
    return load_corpus()


@pytest.fixture(scope="session")
def broken_card() -> RateCardCorpus:
    return load_corpus(SLAB_GAP_CORPUS)


@pytest.fixture(scope="session")
def corpus_documents() -> dict[str, dict]:
    return {
        p.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted(CORPUS.glob("*.json"))
    }
