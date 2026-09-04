"""The committed demo BatchReport is the dashboard lane's input until the
pipeline exists. It must obey every identity the real report will be gated on,
and it must equal what its builder produces so the schema cannot drift silently.
"""

from datetime import date

from leakproof import contract as c
from leakproof.serialize import dumps
from tests.conftest import FIXTURES
from tests.fixtures.build_demo_report import build


def test_fixture_matches_its_builder():
    assert (FIXTURES / "batch_report.demo.json").read_text(encoding="utf-8") == dumps(build())


def test_additivity_identities(demo_report_json):
    r = demo_report_json["rupee_lines"]
    assert r["identified"] == r["claim_ready"] + r["blocked"] + r["not_claimable"]
    assert (
        r["total"] == r["identified"] + r["tax_review"] + r["unexplained"] + r["below_materiality"]
    )
    assert r["not_claimable"] == (
        r["not_claimable_rule"]
        + r["not_claimable_window_expired"]
        + r["not_claimable_evidence_unobtainable"]
    )
    assert r["identified"] == 4_723_000
    assert r["total"] == 4_979_700


def test_rupee_lines_are_sums_of_queue_rows(demo_report_json):
    r = demo_report_json["rupee_lines"]
    sums: dict[str, int] = {}
    counts: dict[str, int] = {}
    for item in demo_report_json["queue"]:
        line = item["state"]["rupee_line"]
        sums[line] = sums.get(line, 0) + item["finding"]["amount_paise"]
        counts[line] = counts.get(line, 0) + 1
    assert (
        sums["claim-ready"] == r["claim_ready"] and counts["claim-ready"] == r["claim_ready_count"]
    )
    assert sums["blocked"] == r["blocked"] and counts["blocked"] == r["blocked_count"]
    assert (
        sums["not-claimable"] == r["not_claimable"]
        and counts["not-claimable"] == r["not_claimable_count"]
    )
    assert sums["tax-review"] == r["tax_review"] and counts["tax-review"] == r["tax_review_count"]
    assert (
        sums["unexplained"] == r["unexplained"] and counts["unexplained"] == r["unexplained_count"]
    )


def test_every_row_has_one_state_and_the_partition_line_it_implies(demo_report_json):
    state_counts: dict[str, int] = {}
    for item in demo_report_json["queue"]:
        cls = c.ErrorClass(item["finding"]["error_class"])
        state = c.State(item["state"]["state"])
        state_counts[state] = state_counts.get(state, 0) + 1
        assert item["state"]["rupee_line"] == c.rupee_line_for(cls, state).value
        assert c.is_material(item["finding"]["amount_paise"])
        assert item["finding"]["source_line_ids"], "every finding cites at least one row"
        claimed = item["finding"]["claimed_line_id"]
        assert claimed is None or claimed in item["finding"]["source_line_ids"]
        assert item["state"]["reason"].strip()
    assert state_counts == {"CLAIM-READY": 7, "BLOCKED": 7, "UNEXPLAINED": 2, "NOT-CLAIMABLE": 4}


def test_queue_sort_order(demo_report_json):
    def key(item):
        group = c.STATE_ORDER.index(c.State(item["state"]["state"]))
        expires = item["assessment"]["deadline"]["expires_on"]
        return (group, expires is None, expires or "", -item["finding"]["amount_paise"])

    keys = [key(i) for i in demo_report_json["queue"]]
    assert keys == sorted(keys)


def test_match_rates_and_dispositions(demo_report_json):
    m = demo_report_json["match_rates"]
    assert m["total_orders"] == 150 and m["matched"] == 141 and m["class6_flagged"] == 6
    assert abs(m["strict"] - 0.94) < 1e-9
    assert abs(m["adjusted"] - 141 / 144) < 1e-9
    d = demo_report_json["dispositions"]
    assert d["quarantine"] + d["uncovered"] + d["out_of_window"] + d["config_error"] == 9
    assert d["config_error"] == 0
    assert len(d["quarantine_reasons"]) == d["quarantine"]


def test_deadlines_respect_as_of(demo_report_json):
    as_of = date.fromisoformat(demo_report_json["as_of"])
    for item in demo_report_json["queue"]:
        dl = item["assessment"]["deadline"]
        if dl["status"] == "expired":
            assert date.fromisoformat(dl["expires_on"]) < as_of
        if dl["status"] == "open":
            assert date.fromisoformat(dl["expires_on"]) >= as_of
            assert dl["days_left"] == (date.fromisoformat(dl["expires_on"]) - as_of).days
