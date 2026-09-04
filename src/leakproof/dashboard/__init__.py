"""Exception-review dashboard from the wireframe markup. Lane G · Tier C · issue #10.

Governed by D16 and the UI section of the design doc. Owns this package.
The wireframe at docs/designs/leakproof-exception-review-wireframe.html is the
starting markup, not a picture of it. serve.py transfers to lane O in Wave 4.
"""

from __future__ import annotations

from pathlib import Path

from leakproof.types import BatchReport


def render(report: BatchReport, *, mode: str) -> str:
    raise NotImplementedError("lane G, issue #10")


def write_demo_html(report: BatchReport, path: Path) -> None:
    raise NotImplementedError("lane G, issue #10")
