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
    def __init__(self) -> None:
        self.entries: list[dict] = []
        self._seq = 1

    def next_seq(self) -> int:
        return self._seq

    def append(self, **kwargs) -> int:
        self.entries.append(kwargs)
        seq = self._seq
        self._seq += 1
        return seq


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


def test_dispatch_gate_action_approve(tmp_path):
    from leakproof.contract import State

    claim_ready_id = next(
        item.finding.finding_id for item in REPORT.queue if item.state.state is State.CLAIM_READY
    )
    log = _FakeAuditLog()
    pack = serve.dispatch_gate_action("approve", claim_ready_id, REPORT, log, tmp_path)
    assert pack is not None
    assert pack.exception_id == claim_ready_id
    assert len(log.entries) == 1


def test_dispatch_gate_action_override(tmp_path):
    from leakproof.contract import State

    blocked_id = next(
        item.finding.finding_id for item in REPORT.queue if item.state.state is State.BLOCKED
    )
    log = _FakeAuditLog()
    pack = serve.dispatch_gate_action("override", blocked_id, REPORT, log, tmp_path)
    assert pack is not None
    assert pack.exception_id == blocked_id
    assert pack.overridden is True
    assert len(log.entries) == 1


def test_dispatch_gate_action_reject():
    from leakproof.contract import AuditAction, State

    claim_ready_id = next(
        item.finding.finding_id for item in REPORT.queue if item.state.state is State.CLAIM_READY
    )
    log = _FakeAuditLog()
    res = serve.dispatch_gate_action("reject", claim_ready_id, REPORT, log, Path("out/claims"))
    assert res is None
    assert len(log.entries) == 1
    assert log.entries[0]["action"] == AuditAction.REJECT


def test_dispatch_gate_action_flag():
    from leakproof.contract import AuditAction, State

    unexplained_id = next(
        item.finding.finding_id for item in REPORT.queue if item.state.state is State.UNEXPLAINED
    )
    log = _FakeAuditLog()
    res = serve.dispatch_gate_action("flag", unexplained_id, REPORT, log, Path("out/claims"))
    assert res is None
    assert len(log.entries) == 1
    assert log.entries[0]["action"] == AuditAction.FLAG


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
        pytest.importorskip("httpx")
        from fastapi.testclient import TestClient

        app = serve.create_app(FIXTURE_PATH)
        return TestClient(app)

    def test_index_renders_served_mode(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "<button" in resp.text

    def test_gate_action_approve_succeeds(self, client):
        from leakproof.contract import State

        claim_ready_id = next(
            item.finding.finding_id
            for item in REPORT.queue
            if item.state.state is State.CLAIM_READY
        )
        resp = client.post(f"/gate/approve/{claim_ready_id}")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_gate_action_unknown_finding_is_404(self, client):
        resp = client.post("/gate/approve/does-not-exist")
        assert resp.status_code == 404

    def test_gate_action_unknown_action_is_400(self, client):
        finding_id = REPORT.queue[1].finding.finding_id
        resp = client.post(f"/gate/bogus/{finding_id}")
        assert resp.status_code == 400
