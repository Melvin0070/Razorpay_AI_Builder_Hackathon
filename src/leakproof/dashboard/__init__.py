"""Exception-review dashboard from the wireframe markup. Lane G · Tier C · issue #10.

Governed by D16 and the UI section of the design doc. Owns this package.
The wireframe at docs/designs/leakproof-exception-review-wireframe.html is the
starting markup, not a picture of it. serve.py transfers to lane O in Wave 4.
"""

from __future__ import annotations

from pathlib import Path

from leakproof.dashboard.template import render_page
from leakproof.serialize import dumps
from leakproof.types import BatchReport


def render(report: BatchReport, *, mode: str) -> str:
    """Full HTML, no external resources of any kind (D16). ``mode`` is
    ``"static"`` (no buttons; an already-gated row shows its result block) or
    ``"served"`` (live approve/override/reject/flag buttons calling
    ``leakproof.gate.*`` through ``dashboard/serve.py``). Everything above the
    ``<!-- gate -->`` marker in each row's detail pane renders identically in
    both modes."""
    return render_page(report, mode=mode)


def write_demo_html(report: BatchReport, path: Path) -> None:
    """``make demo``: static-mode HTML with the report JSON inlined in a
    ``<script type="application/json">`` block, so ``demo.html`` is both the
    self-contained keyless viewer and a record of the exact data it rendered
    from."""
    html = render(report, mode="static")
    # Defensive: a citation URL or drafted-claim quote could in principle contain
    # the literal string "</script>", which would terminate the block early.
    safe_json = dumps(report).replace("</script", "<\\/script")
    data_block = f'<script type="application/json" id="report-data">{safe_json}</script>\n'
    path.write_text(html + data_block, encoding="utf-8")
