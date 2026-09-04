"""Seller profile JSON loader tests (companion format). Lane D · issue #7."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from leakproof.ingest.profile import load_profile

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ingest"


def test_capability_windows_round_trip():
    profile = load_profile(FIXTURES / "seller_profile.json")

    assert profile.seller_id == "SELLER-001"
    assert profile.display_name == "Test Seller Pvt Ltd"
    assert len(profile.capabilities) == 2

    gst, safe_t = profile.capabilities
    assert gst.name == "gst_registered"
    assert gst.holds is True
    assert gst.valid_from == date(2026, 1, 1)
    assert gst.valid_to is None

    assert safe_t.name == "safe_t_enrolled"
    assert safe_t.holds is False
    assert safe_t.valid_from == date(2025, 6, 1)
    assert safe_t.valid_to == date(2026, 5, 31)

    # Round-trip through SellerProfile.capability(): open-ended window applies
    # forever; the closed window only within [valid_from, valid_to].
    assert profile.capability("gst_registered", date(2030, 1, 1)) is True
    assert profile.capability("gst_registered", date(2020, 1, 1)) is None
    assert profile.capability("safe_t_enrolled", date(2025, 12, 1)) is False
    assert profile.capability("safe_t_enrolled", date(2026, 6, 1)) is None
    assert profile.capability("unknown_capability", date(2026, 1, 1)) is None
