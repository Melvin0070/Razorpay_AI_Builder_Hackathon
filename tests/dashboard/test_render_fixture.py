"""Renders the committed demo fixture in both modes and checks the brief's
Tests-required list against it: metrics strip figures, filter-chip counts,
static/served button parity, the D16 above-the-gate parity, and the approved
row's frame-3 block."""

from __future__ import annotations

import json
import re

import pytest

from leakproof.contract import STATE_ORDER
from leakproof.dashboard import render, write_demo_html
from leakproof.serialize import dumps
from tests.fixtures.build_demo_report import build

REPORT = build()

_LINK_URL_RE = re.compile(r'<(?:script[^>]*\bsrc|link[^>]*\bhref)="(https?://[^"]*)"')


@pytest.fixture(scope="module")
def static_html() -> str:
    return render(REPORT, mode="static")


@pytest.fixture(scope="module")
def served_html() -> str:
    return render(REPORT, mode="served")


def test_renders_without_error_in_both_modes(static_html, served_html):
    assert "<title>" in static_html
    assert "<title>" in served_html


def _detail_pane_blocks(html: str) -> list[str]:
    """Each row's full ``<div class="detailpane" ...>...`` block, split at the
    next pane or the trailing ``<script>``."""
    starts = [m.start() for m in re.finditer(r'<div class="detailpane"', html)]
    script_at = html.index("\n<script>")
    bounds = [*starts, script_at]
    return [html[bounds[i] : bounds[i + 1]] for i in range(len(starts))]


def test_every_row_identical_above_the_gate_marker(static_html, served_html):
    """D16: everything above ``<!-- gate -->`` in a given row's detail pane is
    byte-identical between static and served output. Compared per row (by
    position -- both outputs iterate ``report.queue`` in the same order)
    rather than via one whole-document split, because the page necessarily
    carries one detail pane per queue row (see report, Open questions)."""
    static_rows = _detail_pane_blocks(static_html)
    served_rows = _detail_pane_blocks(served_html)
    assert len(static_rows) == len(served_rows) == len(REPORT.queue)
    for s_row, v_row in zip(static_rows, served_rows, strict=True):
        s_above = s_row.split("<!-- gate -->", 1)[0]
        v_above = v_row.split("<!-- gate -->", 1)[0]
        assert s_above == v_above


def test_metrics_strip_figures(static_html):
    for needle in (
        "₹47,230",
        "₹19,400",
        "₹21,600",
        "₹6,230",
        "₹380",
        "₹1,975",
        "₹212",
        "94.0%",
        "97.9%",
    ):
        assert needle in static_html, needle


def test_tier4_not_processed_counts(static_html):
    assert "3</b> quarantined" in static_html
    assert "4</b> uncovered" in static_html
    assert "2</b> out of window" in static_html
    assert "0</b> config errors" in static_html


def test_filter_chip_counts(static_html):
    for chip in ("All 20", "Claim-ready 7", "Blocked 7", "Unexplained 2", "Not claimable 4"):
        assert chip in static_html


def test_queue_groups_appear_in_state_order(static_html):
    positions = [
        static_html.index(f'data-state="{s.value}">{label} ·')
        for s, label in (
            (STATE_ORDER[0], "Claim-ready"),
            (STATE_ORDER[1], "Blocked"),
            (STATE_ORDER[2], "Unexplained"),
            (STATE_ORDER[3], "Not claimable"),
        )
    ]
    assert positions == sorted(positions)


def test_static_mode_has_no_buttons_and_has_the_static_note(static_html):
    assert "<button" not in static_html
    assert "Static export. Run <code>make serve</code>" in static_html


def test_served_mode_has_exactly_one_primary_button_per_state(served_html):
    """ "One primary action per state" (wireframe decision 4A): for one example
    row of each state, the gate region carries exactly one button styled as
    the primary action (pri/over/flag) plus exactly one plain button."""
    panes = list(
        re.finditer(r'<div class="detailpane" data-fid="([^"]+)" data-state="([^"]+)"', served_html)
    )
    seen = set()
    checked = 0
    for i, m in enumerate(panes):
        state = m.group(2)
        if state in seen:
            continue
        end = panes[i + 1].start() if i + 1 < len(panes) else served_html.index("\n<script>")
        pane = served_html[m.start() : end]
        if 'class="approved"' in pane:
            continue  # the approved-fixture row has no buttons at all; a later
            # row of the same state (if any) is still a candidate, so don't mark seen
        seen.add(state)
        buttons = re.findall(r'<button type="button" class="(btn[^"]*)"', pane)
        primary = [b for b in buttons if b != "btn"]
        plain = [b for b in buttons if b == "btn"]
        assert len(primary) == 1, (state, buttons)
        assert len(plain) == 1, (state, buttons)
        checked += 1
    assert checked == len(STATE_ORDER)


def test_approved_fixture_row_renders_frame_3_block(static_html, served_html):
    for html in (static_html, served_html):
        assert "audit seq #118" in html
        assert 'class="approved"' in html
        assert "claims/E-042/" in html


def test_no_external_script_or_link_urls(static_html, served_html):
    assert not _LINK_URL_RE.search(static_html)
    assert not _LINK_URL_RE.search(served_html)
    assert "<script src=" not in static_html and "<script src=" not in served_html
    assert "<link " not in static_html and "<link " not in served_html


def test_write_demo_html_round_trips(tmp_path):
    out = tmp_path / "demo.html"
    write_demo_html(REPORT, out)
    html = out.read_text(encoding="utf-8")
    assert "<button" not in html  # write_demo_html always renders static mode
    m = re.search(r'<script type="application/json" id="report-data">(.*?)</script>', html, re.S)
    assert m is not None
    embedded = json.loads(m.group(1))
    expected = json.loads(dumps(REPORT))
    assert embedded == expected
