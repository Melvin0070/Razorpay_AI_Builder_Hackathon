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


def test_document_has_a_doctype_and_charset(static_html, served_html):
    """finding 2: without a declared charset, a ``file://`` open has no
    ``Content-Type`` header to fall back on -- the export's 555 non-ASCII
    characters (₹ · — … ↑ Δ ≤ →) can render as mojibake under a locale
    default, and no doctype means quirks mode besides."""
    for html in (static_html, served_html):
        assert html.startswith("<!doctype html>")
        assert '<meta charset="utf-8">' in html


def _detail_pane_blocks(html: str) -> list[str]:
    """Each row's full ``<div class="detailpane" ...>...`` block, split at the
    next pane or the trailing ``<script>``."""
    starts = [m.start() for m in re.finditer(r'<div class="detailpane"', html)]
    script_at = html.index("\n<script>")
    bounds = [*starts, script_at]
    return [html[bounds[i] : bounds[i + 1]] for i in range(len(starts))]


_PANE_OR_SCRIPT_RE = re.compile(r'<div class="detailpane"|\n<script>')
_HIDDEN_ATTR_RE = re.compile(r'(<div class="detailpane" data-fid="[^"]*" data-state="[^"]*") hidden>')


def _mask_default_selection(html: str) -> str:
    """Static and served modes intentionally default to *different* rows
    (finding 11: served must not default to an already-gated row, or
    ``make serve`` opens with zero buttons) -- which shows up as a different
    ``hidden`` attribute on a detailpane wrapper and a different ``sel``
    class on the matching queue row. Neither is gate content; it is which
    row happens to be pre-opened, which D16 was never about. The parity
    checks below normalize this one, deliberately mode-dependent, bit of
    markup away before comparing."""
    html = _HIDDEN_ATTR_RE.sub(r"\1>", html)
    return html.replace('class="row sel"', 'class="row"')


def _gate_regions(html: str) -> list[str]:
    """Each row's gate-region content: the substring after ``<!-- gate -->``
    up to the next detail pane (or the trailing ``<script>`` for the last
    row) -- i.e. exactly what ``_gate_region`` produced plus the pane's own
    closing ``</div>``."""
    regions = []
    for m in re.finditer(r"<!-- gate -->", html):
        start = m.end()
        end_m = _PANE_OR_SCRIPT_RE.search(html, start)
        end = end_m.start() if end_m else len(html)
        regions.append(html[start:end])
    return regions


def _elide_gate_regions(html: str) -> str:
    """Same split as ``_gate_regions``, but returns the document with every
    such region blanked out instead of the regions themselves -- what is
    left is exactly the shared chrome (header, strip, chips, queue, trailing
    script) a later change could leak served-only markup into above the
    gate without the per-row test below noticing (finding 6)."""
    out: list[str] = []
    pos = 0
    for m in re.finditer(r"<!-- gate -->", html):
        start = m.end()
        end_m = _PANE_OR_SCRIPT_RE.search(html, start)
        end = end_m.start() if end_m else len(html)
        out.append(html[pos:start])
        out.append("<!--elided-->")
        pos = end
    out.append(html[pos:])
    return "".join(out)


def test_every_row_identical_above_the_gate_marker(static_html, served_html):
    """D16: everything above ``<!-- gate -->`` in a given row's detail pane is
    byte-identical between static and served output (default-selection state
    masked, see ``_mask_default_selection``). Compared per row (by position
    -- both outputs iterate ``report.queue`` in the same order) rather than
    via one whole-document split, because the page necessarily carries one
    detail pane per queue row (see report, Open questions). The whole-
    document tests below additionally guard the region outside any row."""
    static_rows = _detail_pane_blocks(static_html)
    served_rows = _detail_pane_blocks(served_html)
    assert len(static_rows) == len(served_rows) == len(REPORT.queue)
    for s_row, v_row in zip(static_rows, served_rows, strict=True):
        s_above = _mask_default_selection(s_row.split("<!-- gate -->", 1)[0])
        v_above = _mask_default_selection(v_row.split("<!-- gate -->", 1)[0])
        assert s_above == v_above


def test_whole_document_identical_above_the_first_gate_marker(static_html, served_html):
    """finding 6: guards the shared region the per-row test above cannot see
    at all -- header, strip, filter chips and the start of the queue, none
    of which sit inside any row's detail pane."""
    static_prefix = _mask_default_selection(static_html.split("<!-- gate -->", 1)[0])
    served_prefix = _mask_default_selection(served_html.split("<!-- gate -->", 1)[0])
    assert static_prefix == served_prefix


def test_whole_document_identical_with_gate_regions_elided(static_html, served_html):
    """finding 6: with every row's gate region cut out, the two full
    documents -- header, strip, chips, the *entire* queue table, every
    row's above-the-gate content, and the trailing ``<script>`` -- must
    still match byte for byte. A later change threading ``mode`` into the
    queue (not just the gate) would leak served-only markup and be caught
    here even though the per-row test only ever looks inside one pane at a
    time."""
    static_elided = _mask_default_selection(_elide_gate_regions(static_html))
    served_elided = _mask_default_selection(_elide_gate_regions(served_html))
    assert static_elided == served_elided


def test_served_mode_defaults_to_first_row_without_a_gate_record(static_html, served_html):
    """finding 11: the fixture's pre-approved row sorts first in the queue.
    Static mode keeps opening on it (frame 3); served mode -- the pitch-
    video path -- must instead default to the first ungated row, or
    ``make serve`` opens with zero buttons until someone clicks a second
    row."""
    approved = REPORT.queue[0]
    assert approved.gate is not None, "fixture assumption: queue[0] is pre-approved"
    first_ungated = next(item for item in REPORT.queue if item.gate is None)

    def pane_tag(html: str, fid: str) -> str:
        m = re.search(rf'<div class="detailpane" data-fid="{re.escape(fid)}"[^>]*>', html)
        assert m is not None
        return m.group(0)

    assert "hidden" not in pane_tag(static_html, approved.finding.finding_id)
    assert "hidden" in pane_tag(served_html, approved.finding.finding_id)
    assert "hidden" not in pane_tag(served_html, first_ungated.finding.finding_id)


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


def test_static_mode_has_no_buttons_in_the_gate_region_and_has_the_static_note(static_html):
    """D16 / decision 5A: static mode shows the result, not a dead button --
    inside the gate region specifically (finding 12). The assertion is
    scoped to that region because filter chips are real ``<button>``s
    elsewhere on the page in both modes, for keyboard operability; that is
    a different control than the one this rule is about."""
    for region in _gate_regions(static_html):
        assert "<button" not in region
    assert "Static export. Run <code>make serve</code>" in static_html


def test_filter_chips_are_real_buttons_in_both_modes(static_html, served_html):
    for html in (static_html, served_html):
        assert '<button type="button" class="chipf on" data-state="all"' in html
        assert '<button type="button" class="chipf" data-state="BLOCKED"' in html


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
    for region in _gate_regions(html):
        assert "<button" not in region  # write_demo_html always renders static mode
    assert html.startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in html
    m = re.search(r'<script type="application/json" id="report-data">(.*?)</script>', html, re.S)
    assert m is not None
    embedded = json.loads(m.group(1))
    expected = json.loads(dumps(REPORT))
    assert embedded == expected
