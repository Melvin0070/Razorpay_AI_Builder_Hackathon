"""D12: once frozen, the labels file cannot change without the ADR-0003 procedure."""

import hashlib

import pytest

from leakproof import contract as c
from tests.conftest import ROOT


def test_frozen_labels_checksum():
    if c.FROZEN_LABELS_SHA256 is None:
        pytest.skip("labels not frozen yet; the integrator freezes them at the Wave 1 close")
    path = ROOT / c.LABELS_FILE
    assert path.exists(), f"{c.LABELS_FILE} missing after freeze"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == c.FROZEN_LABELS_SHA256, "labels changed after the freeze (see ADR-0003)"
