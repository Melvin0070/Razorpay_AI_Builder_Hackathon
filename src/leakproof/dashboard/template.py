"""HTML assembly. Structure lifted from
``docs/designs/leakproof-exception-review-wireframe.html``: header, four-tier
metrics strip, filter chips + grouped queue table, detail pane (source rows ->
recomputation -> evidence checklist -> drafted claim -> gate), and the three
frame-4 boundary states. See the module docstring in ``__init__.py`` for the
public entry points.
"""

from __future__ import annotations

import re

from leakproof.contract import (
    MATERIALITY_FLOOR_PAISE,
    STATE_ORDER,
    ErrorClass,
    EvidenceStatus,
    Mechanism,
    RupeeLine,
    State,
    WindowStatus,
)
from leakproof.dashboard.css import CSS
from leakproof.dashboard.format import (
    FILTER_LABELS,
    class_column,
    class_label,
    file_by,
    format_date_short,
    format_pct,
    format_rupees,
    format_rupees_bare,
    format_rupees_paise,
    named_blocker,
    override_consequence_lead,
    override_label,
    oxford_join,
    state_css,
)
from leakproof.dashboard.html_utils import esc, js_str
from leakproof.types import BatchReport, Deadline, EligibilityCheck, Finding, TriagedFinding

# --------------------------------------------------------------------------- #
# Page assembly
# --------------------------------------------------------------------------- #


def render_page(report: BatchReport, *, mode: str) -> str:
    if mode not in ("static", "served"):
        raise ValueError(f"mode must be 'static' or 'served', got {mode!r}")

    grouped = _group_by_state(report.queue)
    boundary = _boundary_state(report)
    default_fid = _default_fid(report, mode)

    body = [
        '<div class="frame">',
        _header(report),
        f'<div class="metrics">{_metrics(report)}</div>',
    ]
    if boundary is not None:
        body.append(_boundary_box(report, boundary))
    else:
        body.append(
            '<div class="cols">'
            f'<div class="list">{_filters(grouped, len(report.queue))}'
            f"{_queue_table(grouped, default_fid)}</div>"
            f'<div class="detail">{_detail_panes(report, mode, default_fid)}</div>'
            "</div>"
        )
    body.append("</div>")
    body.append(_script())

    doc = [
        "<!doctype html>",
        "<html>",
        "<head>",
        '<meta charset="utf-8">',
        "<title>LeakProof — exception review</title>",
        f"<style>{CSS}</style>",
        "</head>",
        "<body>",
        *body,
        "</body>",
        "</html>",
    ]
    return "\n".join(doc) + "\n"


def _default_fid(report: BatchReport, mode: str) -> str | None:
    """The row shown open by default. Static mode keeps the wireframe's
    plain first-row selection; served mode -- the pitch-video path -- must
    not default to a row that already has a gate record, or ``make serve``
    opens with zero buttons until someone clicks a second row."""
    if not report.queue:
        return None
    if mode == "served":
        for item in report.queue:
            if item.gate is None:
                return item.finding.finding_id
    return report.queue[0].finding.finding_id


def _group_by_state(
    queue: tuple[TriagedFinding, ...],
) -> dict[State, list[TriagedFinding]]:
    grouped: dict[State, list[TriagedFinding]] = {s: [] for s in STATE_ORDER}
    for item in queue:
        grouped[item.state.state].append(item)
    return grouped


def _boundary_state(report: BatchReport) -> str | None:
    """Which of the three frame-4 empty/boundary narratives applies, or None
    for the normal queue. Order matters: an unparsed batch is also, trivially,
    a batch with no covered rows, so "nothing parsed" is checked first.

    ``dispositions.quarantine`` counts malformed settlement *rows*;
    ``order_count`` counts *orders*. Comparing them directly (rows >= orders)
    misfires on a clean batch that just has a few noisy leftover rows -- e.g.
    2 orders, 3 quarantined header/footer lines, both orders matched fine --
    which is a "zero exceptions" batch, not an unparsed one. "Nothing parsed"
    instead means literally nothing came out of matching: some row was
    quarantined and not one order matched."""
    if report.queue:
        return None
    d, m = report.dispositions, report.match_rates
    if report.order_count > 0 and d.quarantine > 0 and m.matched == 0:
        return "unparsed"
    if report.order_count > 0 and d.uncovered >= report.order_count:
        return "uncovered"
    return "zero"


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #


def _header(report: BatchReport) -> str:
    audit = f" · audit #{esc(report.audit_head_hash[:4])}…" if report.audit_head_hash else ""
    coverage = (
        f"coverage {format_date_short(report.coverage.start)}"
        f"–{format_date_short(report.coverage.end)}"
    )
    subline = (
        f"{report.order_count} orders · {esc(report.marketplace)} · {coverage} · "
        f"as_of {report.as_of.isoformat()}{audit}"
    )
    return (
        "<header>"
        f"<h1>LEAKPROOF · Batch {esc(report.batch_id)}</h1>"
        f'<div class="batch mono">{subline}</div>'
        "</header>"
    )


# --------------------------------------------------------------------------- #
# Metrics strip (deliverable 2)
# --------------------------------------------------------------------------- #


def _metrics(report: BatchReport) -> str:
    return _tier1(report) + _tier2(report) + _tier3(report) + _tier4(report)


def _tier1(report: BatchReport) -> str:
    return (
        '<div class="t1"><div class="k">₹ identified</div>'
        f'<div class="v">{format_rupees(report.rupee_lines.identified)}</div></div>'
    )


def _tier2(report: BatchReport) -> str:
    r = report.rupee_lines
    identified = r.identified
    state_counts = {s: 0 for s in STATE_ORDER}
    for item in report.queue:
        state_counts[item.state.state] += 1

    if identified > 0:
        ready_pct = r.claim_ready / identified * 100
        block_pct = r.blocked / identified * 100
        noclaim_pct = 100 - ready_pct - block_pct
        bar = (
            '<div class="bar">'
            f'<span class="s-ready" style="width:{ready_pct:.2f}%"></span>'
            f'<span class="s-block" style="width:{block_pct:.2f}%"></span>'
            f'<span class="s-noclaim" style="width:{noclaim_pct:.2f}%"></span>'
            "</div>"
        )
    else:
        bar = (
            '<div class="bar" style="height:14px;border-color:var(--rule)">'
            '<span style="width:100%;background:var(--bg)"></span></div>'
        )

    # "window expired" is pinned bold regardless of which reason is largest
    # (design doc: "the line that makes a seller act") -- not the biggest
    # figure, which drifts with the data (finding 7).
    nc_reasons = (
        (r.not_claimable_rule, "excluded by rule"),
        (r.not_claimable_window_expired, "window expired"),
        (r.not_claimable_evidence_unobtainable, "evidence unobtainable"),
    )
    nc_sub = " · ".join(
        f"<b>{format_rupees(amt)} {label}</b>"
        if label == "window expired"
        else f"{format_rupees(amt)} {label}"
        for amt, label in nc_reasons
    )

    legend = (
        '<div class="legend">'
        '<div><div class="lab">claim-ready</div>'
        f'<div class="amt">{format_rupees(r.claim_ready)}</div>'
        f'<div class="sub">{state_counts[State.CLAIM_READY]} claims, evidence complete</div></div>'
        '<div><div class="lab">blocked</div>'
        f'<div class="amt">{format_rupees(r.blocked)}</div>'
        f'<div class="sub">{state_counts[State.BLOCKED]} — named blocker each</div></div>'
        '<div><div class="lab">not claimable</div>'
        f'<div class="amt">{format_rupees(r.not_claimable)}</div>'
        f'<div class="sub">{nc_sub}</div></div>'
        "</div>"
    )
    return bar + legend


def _tier3(report: BatchReport) -> str:
    r = report.rupee_lines
    floor = format_rupees(MATERIALITY_FLOOR_PAISE)
    return (
        '<div class="t3">'
        f'<div><span class="lab">tax-review</span> <span class="amt">{format_rupees(r.tax_review)}</span>'
        f" · {r.tax_review_count} · CA export</div>"
        f'<div><span class="lab">unexplained</span> <span class="amt">{format_rupees(r.unexplained)}</span>'
        f" · {r.unexplained_count}</div>"
        f'<div><span class="lab">below {floor}</span> <span class="amt">{format_rupees(r.below_materiality)}</span>'
        f" · {r.below_materiality_rows} rows, aggregated</div>"
        f'<div style="margin-left:auto;color:var(--ink-3)">total discrepancy '
        f'<span class="num">{format_rupees(r.total)}</span></div>'
        "</div>"
    )


def _tier4(report: BatchReport) -> str:
    m = report.match_rates
    d = report.dispositions
    not_processed = d.quarantine + d.uncovered + d.out_of_window + d.config_error
    return (
        '<div class="t4">'
        f'<div>match rate <b class="num">{format_pct(m.strict)}</b> strict · '
        f'<b class="num">{format_pct(m.adjusted)}</b> adjusted '
        f'<span style="color:var(--ink-3)">(Δ = {m.class6_flagged} unpaid orders, '
        "excluded from adjusted)</span></div>"
        f"<div>{not_processed} rows not processed: "
        f'<b class="num">{d.quarantine}</b> quarantined · '
        f'<b class="num">{d.uncovered}</b> uncovered · '
        f'<b class="num">{d.out_of_window}</b> out of window · '
        f'<b class="num">{d.config_error}</b> config errors</div>'
        "</div>"
    )


# --------------------------------------------------------------------------- #
# Filter chips + queue table (deliverable 3)
# --------------------------------------------------------------------------- #


def _filters(grouped: dict[State, list[TriagedFinding]], total: int) -> str:
    # Real <button>s, not <span onclick>, so the filter row is keyboard-
    # operable (finding 12). These are outside the <!-- gate --> region and
    # are not part of D16's "static mode has no buttons" rule, which is
    # about the per-row gate, not chrome that filters an already-rendered
    # page in both modes alike.
    chips = [
        '<button type="button" class="chipf on" data-state="all" onclick="lpFilter(this)">'
        f"All {total}</button>"
    ]
    for s in STATE_ORDER:
        chips.append(
            f'<button type="button" class="chipf" data-state="{s.value}" onclick="lpFilter(this)">'
            f"{FILTER_LABELS[s]} {len(grouped[s])}</button>"
        )
    chips_html = "".join(chips)
    return (
        f'<div class="filters">{chips_html}'
        '<span style="margin-left:auto">grouped by state · deadline ↑ · nulls last · ₹ ↓</span>'
        "</div>"
    )


def _group_header(state: State, rows: list[TriagedFinding]) -> str:
    primary_line = {
        State.CLAIM_READY: RupeeLine.CLAIM_READY,
        State.BLOCKED: RupeeLine.BLOCKED,
        State.UNEXPLAINED: RupeeLine.UNEXPLAINED,
        State.NOT_CLAIMABLE: RupeeLine.NOT_CLAIMABLE,
    }[state]
    primary_amt = sum(i.finding.amount_paise for i in rows if i.state.rupee_line is primary_line)
    extras: dict[RupeeLine, int] = {}
    for i in rows:
        if i.state.rupee_line is not primary_line:
            extras[i.state.rupee_line] = extras.get(i.state.rupee_line, 0) + i.finding.amount_paise
    note = ""
    if extras:
        parts = [f"+ {format_rupees(amt)} {line.value}" for line, amt in extras.items()]
        note = (
            f' <span style="text-transform:none;letter-spacing:0">'
            f"({', '.join(parts)}, reported on its own line)</span>"
        )
    return (
        f'<tr><td colspan="5" class="grp" data-state="{state.value}">'
        f"{FILTER_LABELS[state]} · {len(rows)} · {format_rupees(primary_amt)}{note}</td></tr>"
    )


def _queue_table(grouped: dict[State, list[TriagedFinding]], default_fid: str | None) -> str:
    rows_html = []
    for s in STATE_ORDER:
        rows = grouped[s]
        if not rows:
            continue
        rows_html.append(_group_header(s, rows))
        for item in rows:
            rows_html.append(_queue_row(item, selected=item.finding.finding_id == default_fid))
    return (
        "<table>"
        '<tr><th>Order</th><th>Class</th><th style="text-align:right">₹</th>'
        "<th>Evidence status</th><th>File by</th></tr>"
        f"{''.join(rows_html)}"
        "</table>"
    )


_DAYS_LEFT_RE = re.compile(r"^(\d+d) · (.+)$")


def _file_by_html(item: TriagedFinding) -> str:
    """``file_by`` with the day-count bolded, matching the wireframe's
    ``<b>6d</b> · 02 Sep`` (the day count is the only part that changes as
    ``as_of`` moves, so it is the part that draws the eye)."""
    text = file_by(item.assessment.deadline, item.state)
    m = _DAYS_LEFT_RE.match(text)
    if m:
        return f"<b>{esc(m.group(1))}</b> · {esc(m.group(2))}"
    return esc(text)


def _queue_row(item: TriagedFinding, *, selected: bool) -> str:
    f, st = item.finding, item.state
    sel_cls = " sel" if selected else ""
    why = f'<span class="why">{esc(st.reason)}</span>' if st.state is not State.CLAIM_READY else ""
    fid = esc(f.finding_id)
    return (
        f'<tr class="row{sel_cls}" data-fid="{fid}" data-state="{st.state.value}" '
        f"onclick=\"lpSelect('{esc(js_str(f.finding_id))}')\">"
        f'<td class="mono">{esc(f.order_id)}</td>'
        f"<td>{esc(class_column(f.error_class))}</td>"
        f'<td class="amt">{format_rupees_bare(f.amount_paise)}</td>'
        f'<td><span class="st {state_css(st.state)}">{st.state.value}</span>{why}</td>'
        f'<td class="ddl">{_file_by_html(item)}</td>'
        "</tr>"
    )


# --------------------------------------------------------------------------- #
# Detail pane (deliverable 4): source rows -> recomputation -> evidence
# checklist -> drafted claim -> <!-- gate --> -> gate region.
# --------------------------------------------------------------------------- #


def _detail_panes(report: BatchReport, mode: str, default_fid: str | None) -> str:
    return "".join(
        _detail_pane(item, mode, is_default=item.finding.finding_id == default_fid)
        for item in report.queue
    )


def _detail_pane(item: TriagedFinding, mode: str, *, is_default: bool) -> str:
    f, st = item.finding, item.state
    hidden = "" if is_default else " hidden"
    fid = esc(f.finding_id)
    parts = [
        f'<div class="detailpane" data-fid="{fid}" data-state="{st.state.value}"{hidden}>',
        f"<h2>{esc(class_label(f.error_class))} · {format_rupees(f.amount_paise)}</h2>",
        f'<div class="sub">{_finding_subline(f)}</div>',
        f'<div style="margin-bottom:11px"><span class="st {state_css(st.state)}">{st.state.value}'
        f'</span> <span class="why">{esc(st.reason)}</span></div>',
        _source_rows(f),
        _recomputation(f),
        _evidence_checklist(item),
        _drafted_claim(item),
        "<!-- gate -->",
        _gate_region(item, mode),
        "</div>",
    ]
    return "".join(parts)


def _finding_subline(f: Finding) -> str:
    """ "Order X · SKU Y · Z", omitting a missing SKU or category (and its
    separator) instead of leaving a dangling "SKU  · " -- what lane J's
    class-6 absence findings and orphan rows produce (finding 12)."""
    parts = [f"Order {esc(f.order_id)}"]
    if f.sku:
        parts.append(f"SKU {esc(f.sku)}")
    if f.category_id:
        parts.append(esc(f.category_id))
    return " · ".join(parts)


def _source_rows(f: Finding) -> str:
    lines = "".join(
        f'<div class="cite">{"<b>" if lid == f.claimed_line_id else ""}{esc(lid)}'
        f"{' (claimed)' if lid == f.claimed_line_id else ''}"
        f"{'</b>' if lid == f.claimed_line_id else ''}</div>"
        for lid in f.source_line_ids
    )
    return (
        f'<div class="sec"><div class="h">Source rows ({len(f.source_line_ids)})</div>'
        f'<div class="b">{lines}</div></div>'
    )


def _recomputation(f: Finding) -> str:
    rows = f.recomputation
    lines = []
    for i, row in enumerate(rows):
        bold = i == len(rows) - 1
        text = esc(row.label)
        if row.amount_paise is not None:
            neg = row.amount_paise < 0
            amt = format_rupees_paise(row.amount_paise)
            span = f'<span class="neg">{esc(amt)}</span>' if neg else esc(amt)
            text = f"{text} → {span}"
        if row.note:
            text = f'{text} <span class="note">({esc(row.note)})</span>'
        if bold:
            text = f"<b>{text}</b>"
        lines.append(f'<div class="row">{text}</div>')
    return (
        '<div class="sec"><div class="h">Recomputation</div>'
        f'<div class="b diff">{"".join(lines)}</div></div>'
    )


def _evidence_checklist(item: TriagedFinding) -> str:
    """The wireframe deliberately mixes eligibility rule checks in with
    evidence requirements (design doc, "UI"): both are ☑/☐ facts the queue
    row's state was decided on, and a rule that disqualified the claim must
    show as unchecked, not buried in a why-line with an unrelated ☑ beside
    it (finding 3)."""
    f, assessment = item.finding, item.assessment
    mech = f.mechanism
    header = "Evidence" if mech is Mechanism.NONE else f"Evidence — {mech.value} requires"
    lines = [_eligibility_line(c) for c in assessment.eligibility]
    for e in assessment.evidence:
        cls = "ok" if e.status is EvidenceStatus.SATISFIED else "miss"
        # PENDING (requested, may still arrive) and MISSING (permanently
        # unobtainable) both render an unchecked box; without a structural
        # marker the two read the same unless the free-text note happens to
        # say which (finding 12) -- a "pending" tag makes it a fact of the
        # markup, not something resting on note text a producer might omit.
        tag = '<span class="pend">pending</span>' if e.status is EvidenceStatus.PENDING else ""
        text = esc(e.requirement)
        if e.note:
            text = f"{text} ({esc(e.note)})"
        lines.append(f'<div class="evreq"><span class="{cls}">{text}</span>{tag}</div>')
    lines.append(_window_evidence_line(assessment.deadline))
    return (
        f'<div class="sec"><div class="h">{esc(header)}</div>'
        f'<div class="b">{"".join(lines)}</div></div>'
    )


def _eligibility_line(check: EligibilityCheck) -> str:
    cls = "ok" if check.passed else "miss"
    tag = "" if check.citation.verified else '<span class="unver">rule unverified</span>'
    return f'<div class="evreq"><span class="{cls}">{esc(check.description)}</span>{tag}</div>'


def _window_evidence_line(deadline: Deadline) -> str:
    if deadline.status is WindowStatus.NOT_APPLICABLE:
        return ""
    ok = deadline.status is WindowStatus.OPEN
    cls = "ok" if ok else "miss"
    label = "Within filing window"
    if deadline.starts_on is not None:
        label = f"{label} (event {format_date_short(deadline.starts_on)})"
    tag = ""
    link = ""
    if deadline.citation is not None:
        if not deadline.citation.verified:
            tag = '<span class="unver">rule unverified</span>'
        link = (
            f' <a class="cite-link" href="{esc(deadline.citation.url)}" '
            f'target="_blank" rel="noopener">[{esc(deadline.citation.label)}]</a>'
        )
    return f'<div class="evreq"><span class="{cls}">{esc(label)}</span>{tag}{link}</div>'


def _drafted_claim(item: TriagedFinding) -> str:
    body = f'"{esc(item.draft.rendered_text)}"' if item.draft is not None else "not drafted"
    return (
        '<div class="sec"><div class="h">Drafted claim (agent-written, not filed)</div>'
        f'<div class="b claim">{body}</div></div>'
    )


# --------------------------------------------------------------------------- #
# Gate region (deliverable 5). Everything above ``<!-- gate -->`` is identical
# across modes; only this function's output differs, and only when the row
# carries no gate record (an already-gated row renders the same approved
# block regardless of mode).
# --------------------------------------------------------------------------- #


def _gate_region(item: TriagedFinding, mode: str) -> str:
    if item.gate is not None:
        return f'<div class="gate">{_approved_block(item)}</div>'
    if mode == "static":
        return f'<div class="gate">{_static_note()}</div>'
    return f'<div class="gate">{_gate_buttons(item)}</div>'


def _artifact_file(path: str | None, filename: str) -> str:
    """Join an artifact directory and a filename without assuming the path
    already ends in ``/`` (finding 8: the fixture's own path happens to, but
    a future ``GateRecord.artifact_path`` need not)."""
    if not path:
        return "—"
    sep = "" if path.endswith("/") else "/"
    return f"{path}{sep}{filename}"


def _approved_block(item: TriagedFinding) -> str:
    finding, gate = item.finding, item.gate
    assert gate is not None
    label = "Overridden" if gate.overridden else "Approved"
    path = gate.artifact_path
    written_to = esc(path) if path else "—"
    claim_text = (
        f'"{esc(item.draft.rendered_text)}" <i>(full, selectable)</i>'
        if item.draft is not None
        else "not drafted"
    )
    return (
        '<div class="approved">'
        f'<div class="h">{label} · audit seq #{gate.audit_seq}</div>'
        '<div class="b">'
        f'<div class="row"><div class="k">claim text</div><div>{claim_text}</div></div>'
        f'<div class="row"><div class="k">cited rows</div>'
        f'<div class="mono">{len(finding.source_line_ids)} rows · '
        f"{esc(_artifact_file(path, 'cited_rows.csv'))}</div></div>"
        f'<div class="row"><div class="k">recomputation</div>'
        f'<div class="mono">{esc(_artifact_file(path, "recomputation.csv"))}</div></div>'
        f'<div class="row"><div class="k">written to</div><div class="mono">{written_to}</div></div>'
        "</div></div>"
    )


def _static_note() -> str:
    return (
        '<div class="staticnote">'
        "Static export. Run <code>make serve</code> to approve, override or reject.<br>"
        "Everything above this line is exactly what the live tool shows."
        "</div>"
    )


def _gate_buttons(item: TriagedFinding) -> str:
    f, st = item.finding, item.state
    # esc(js_str(...)): js_str alone only escapes \, ' and newline for the JS
    # string literal -- a stray " in a finding_id (order_id/line_id sourced
    # from a settlement file's own basename, D19) would still close the
    # surrounding onclick="..." attribute. esc() afterwards neutralises that
    # (and any <, &) once the JS-level escaping is in place (finding 1).
    fid_js = esc(js_str(f.finding_id))
    fid = esc(f.finding_id)
    result_div = f'<div class="gateresult" data-fid="{fid}" hidden></div>'

    if st.state is State.CLAIM_READY:
        return (
            '<div class="btns">'
            f'<button type="button" class="btn pri" onclick="lpGate(\'approve\',\'{fid_js}\',this)">'
            "APPROVE &amp; QUEUE</button>"
            f'<button type="button" class="btn" onclick="lpGate(\'reject\',\'{fid_js}\',this)">REJECT</button>'
            "</div>"
            '<div class="conseq">Writes a claim pack and one audit entry. '
            "Nothing is filed. Approving twice is a no-op.</div>"
            f"{result_div}"
        )

    if st.state is State.UNEXPLAINED:
        basis = f.unexplained_basis.value if f.unexplained_basis is not None else "unknown"
        return (
            '<div class="btns">'
            f'<button type="button" class="btn flag" onclick="lpGate(\'flag\',\'{fid_js}\',this)">'
            "FLAG FOR FOLLOW-UP</button>"
            f'<button type="button" class="btn" onclick="lpGate(\'reject\',\'{fid_js}\',this)">DISMISS</button>'
            "</div>"
            '<div class="conseq">Mechanism is <span class="mono">none</span>, so there is no claim '
            "to draft and no pack to write. Writes one audit entry carrying the basis "
            f'(<span class="mono">{esc(basis)}</span>).</div>'
            f"{result_div}"
        )

    # BLOCKED or NOT-CLAIMABLE: override + reject (design decision 4A, ADR-0007).
    label = override_label(st.state, st.blocker_kind, st.not_claimable_reason)
    lead = override_consequence_lead(st.state, st.blocker_kind, st.not_claimable_reason)
    item_name = named_blocker(st.reason)
    return (
        '<div class="btns">'
        f'<button type="button" class="btn over" onclick="lpGate(\'override\',\'{fid_js}\',this)">'
        f"{esc(label)}</button>"
        f'<button type="button" class="btn" onclick="lpGate(\'reject\',\'{fid_js}\',this)">REJECT</button>'
        "</div>"
        f'<div class="conseq">{esc(lead)}: <b>{esc(item_name)}</b>.<br>'
        'Pack marked <b>OVERRIDDEN</b>. Recorded as <span class="mono">approve_override</span> '
        'with <span class="mono">state_before</span>. Never enters ₹ claim-ready.</div>'
        f"{result_div}"
    )


# --------------------------------------------------------------------------- #
# Boundary states (deliverable 6, wireframe frame 4). Rendered from the report
# data alone, in place of the queue/detail columns; the metrics strip above
# still renders normally (it is already all-zeros in these cases).
# --------------------------------------------------------------------------- #


def _boundary_box(report: BatchReport, kind: str) -> str:
    if kind == "zero":
        return _boundary_zero(report)
    if kind == "uncovered":
        return _boundary_uncovered(report)
    return _boundary_unparsed(report)


def _boundary_zero(report: BatchReport) -> str:
    r = report.rupee_lines
    floor = format_rupees(MATERIALITY_FLOOR_PAISE)
    # "; " because class 5's own label ("Refund, fee not reversed") carries
    # a comma; joining the list on commas too would read as a longer,
    # wrongly-split list (finding 12).
    checked = oxford_join([class_label(c) for c in ErrorClass], sep="; ")
    return (
        '<div class="emptybox"><div class="headline">'
        f"<b>{report.order_count} orders reconciled. No discrepancies above {floor}.</b>"
        '<div class="conseq">Every settlement line matched a rate-card rule. '
        f"{format_rupees(r.below_materiality)} in below-materiality differences was aggregated "
        f"and excluded, over {r.below_materiality_rows} rows. Checked: {esc(checked)}.</div>"
        "</div></div>"
    )


def _boundary_uncovered(report: BatchReport) -> str:
    cov = report.rate_card_coverage
    cats = ", ".join(f'<span class="mono">{esc(c)}</span>' for c in cov.categories)
    d = report.dispositions
    return (
        '<div class="emptybox"><div class="headline">'
        "<b>No orders in a covered category.</b>"
        f'<div class="conseq">The rate-card corpus covers {len(cov.categories)} '
        f"categories: {cats}. {d.uncovered} of {report.order_count} orders fall outside "
        "declared coverage. Detectors 1 and 2 need a rule to compare against, so they did "
        "not run on those rows. Nothing was guessed.</div>"
        "</div></div>"
    )


def _boundary_unparsed(report: BatchReport) -> str:
    d = report.dispositions
    reasons = d.quarantine_reasons[:2]
    reason_lines = "".join(
        f'<div class="cite">{esc(qr.line_id)} · {esc(qr.reason)}</div>' for qr in reasons
    )
    more = len(d.quarantine_reasons) - len(reasons)
    if more > 0:
        # "same reason" is only true when the reasons actually agree -- don't
        # assert it for a batch quarantined for several different causes
        # (finding 10).
        rest_reasons = {qr.reason for qr in d.quarantine_reasons[len(reasons) :]}
        shown_reasons = {qr.reason for qr in reasons}
        same_reason = len(rest_reasons | shown_reasons) == 1
        suffix = ", same reason" if same_reason else ""
        reason_lines += f'<div class="cite" style="color:var(--ink-3)">…{more} more{suffix}</div>'
    hint = (
        f'<div class="conseq" style="margin-top:8px"><b>Likely cause:</b> {esc(d.hint)}</div>'
        if d.hint
        else ""
    )
    return (
        '<div class="emptybox"><div class="headline">'
        "<b>The settlement file did not parse.</b>"
        f'<div class="conseq">All {d.quarantine} rows quarantined. Quarantined rows stay in '
        f"the match-rate denominator (D7), which is why the rate reads "
        f"{format_pct(report.match_rates.strict)} rather than being hidden.</div>"
        f'<div style="margin-top:8px">{reason_lines}</div>'
        f"{hint}"
        "</div></div>"
    )


# --------------------------------------------------------------------------- #
# Inline JS: row selection, filter chips, served gate calls (deliverable 1).
# --------------------------------------------------------------------------- #


def _script() -> str:
    return """
<script>
function lpSelect(id){
  document.querySelectorAll('.detailpane').forEach(function(p){
    p.hidden = p.getAttribute('data-fid') !== id;
  });
  document.querySelectorAll('tr.row').forEach(function(r){
    r.classList.toggle('sel', r.getAttribute('data-fid') === id);
  });
}
function lpFilter(chip){
  var state = chip.getAttribute('data-state');
  document.querySelectorAll('.chipf').forEach(function(c){
    c.classList.toggle('on', c === chip);
  });
  document.querySelectorAll('tr.row').forEach(function(r){
    r.hidden = state !== 'all' && r.getAttribute('data-state') !== state;
  });
  document.querySelectorAll('.grp').forEach(function(g){
    g.hidden = state !== 'all' && g.getAttribute('data-state') !== state;
  });
}
function lpGate(action, id, btn){
  btn.disabled = true;
  var box = document.querySelector('.gateresult[data-fid="' + id + '"]');
  fetch('/gate/' + encodeURIComponent(action) + '/' + encodeURIComponent(id), {method: 'POST'})
    .then(function(r){
      return r.json().catch(function(){ return {}; }).then(function(body){
        return {status: r.status, body: body};
      });
    })
    .then(function(res){
      btn.disabled = false;
      if(!box) return;
      box.hidden = false;
      if(res.status === 200){
        box.textContent = 'Done.';
      } else {
        box.textContent = 'Not available yet (HTTP ' + res.status + '): ' +
          (res.body && res.body.detail ? res.body.detail : '');
      }
    })
    .catch(function(e){
      btn.disabled = false;
      if(box){ box.hidden = false; box.textContent = 'Request failed: ' + e; }
    });
}
</script>
"""
