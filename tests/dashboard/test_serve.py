"""``dashboard/serve.py``. The dispatch logic and the lazy-import path are
framework-free and always run (no ``serve`` extra needed); the actual FastAPI
endpoints are only exercised when the extra happens to be installed, via
``pytest.importorskip`` -- this repo's ``make verify`` never installs it
(brief, exit criteria), so that class is expected to be skipped there. See
the report, "What broke and how you got out": this was not smoke-tested
against a live server in this environment."""

from __future__ import annotations

from pathlib import Path

import pytest

from leakproof.dashboard import serve
from leakproof.dashboard.load import load_report
from tests.fixtures.build_demo_report import build

REPORT = build()
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "batch_report.demo.json"


class _FakeAuditLog:
    """Stands in for ``leakproof.audit.AuditLog`` in dispatch tests: the real
    one also raises ``NotImplementedError`` from its own methods, and every
    ``leakproof.gate.*`` stub raises before touching the log at all, so a
    bare object with no behaviour is enough to prove that."""


def test_create_app_import_error_message_when_fastapi_missing():
    try:
        import fastapi  # noqa: F401

        pytest.skip("fastapi is installed in this environment; see the served-mode class below")
    except ImportError:
        pass
    with pytest.raises(ImportError, match=r"serve.*extra"):
        serve.create_app(FIXTURE_PATH)


def test_find_finding_locates_a_real_row_and_misses_an_unknown_one():
    known = REPORT.queue[0].finding.finding_id
    assert serve.find_finding(REPORT, known) is not None
    assert serve.find_finding(REPORT, "nonexistent|1|-") is None


@pytest.mark.parametrize("action", ["approve", "override", "reject", "flag"])
def test_dispatch_gate_action_surfaces_not_implemented(action):
    """Every gate action is still a Wave-4 stub; the route (below) translates
    this into HTTP 501 naming the lane and issue."""
    finding_id = REPORT.queue[0].finding.finding_id
    with pytest.raises(NotImplementedError, match="lane O"):
        serve.dispatch_gate_action(action, finding_id, REPORT, _FakeAuditLog(), Path("out/claims"))


def test_dispatch_gate_action_unknown_action():
    finding_id = REPORT.queue[0].finding.finding_id
    with pytest.raises(ValueError, match="unknown gate action"):
        serve.dispatch_gate_action("bogus", finding_id, REPORT, _FakeAuditLog(), Path("."))


def test_dispatch_gate_action_unknown_finding():
    with pytest.raises(KeyError, match="unknown finding_id"):
        serve.dispatch_gate_action("approve", "nope|1|-", REPORT, _FakeAuditLog(), Path("."))


def test_load_report_round_trips_the_fixture():
    """Full equality, not a handful of sampled fields (finding 9): ``load.py``
    uses explicit kwargs, so a new ``BatchReport`` field with a default would
    otherwise be silently dropped on load while every field-by-field
    assertion kept passing."""
    assert load_report(FIXTURE_PATH) == REPORT


# --------------------------------------------------------------------------- #
# Full endpoint behaviour: only meaningful, and only run, when fastapi is
# actually importable. `make verify` in this worktree never installs the
# `serve` extra (brief, exit criteria), so this class is expected to skip --
# the skip happens inside the fixture, not at module import time, so it does
# not take the framework-free tests above down with it.
# --------------------------------------------------------------------------- #


class TestServedEndpoints:
    @pytest.fixture
    def client(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        app = serve.create_app(FIXTURE_PATH)
        return TestClient(app)

    def test_index_renders_served_mode(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "<button" in resp.text

    def test_gate_action_returns_501_with_lane_and_issue(self, client):
        finding_id = REPORT.queue[1].finding.finding_id  # not the pre-approved row
        resp = client.post(f"/gate/approve/{finding_id}")
        assert resp.status_code == 501
        assert "lane O" in resp.json()["detail"]

    def test_gate_action_unknown_finding_is_404(self, client):
        resp = client.post("/gate/approve/does-not-exist")
        assert resp.status_code == 404

    def test_gate_action_unknown_action_is_400(self, client):
        finding_id = REPORT.queue[1].finding.finding_id
        resp = client.post(f"/gate/bogus/{finding_id}")
        assert resp.status_code == 400
