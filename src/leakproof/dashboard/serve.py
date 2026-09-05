"""FastAPI shell for ``make serve`` (D16, D8). ``GET /`` renders the report in
served mode; ``POST /gate/{action}/{finding_id}`` calls the matching
``leakproof.gate.*`` function, which raises ``NotImplementedError`` until
lane O lands in Wave 4 (this module's ownership transfers to lane O then, per
the strategy doc).

FastAPI is imported lazily, inside ``create_app``, so ``import
leakproof.dashboard.serve`` and ``make verify`` never need the ``serve``
extra -- only ``make serve`` does.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from leakproof import gate
from leakproof.audit import AuditLog
from leakproof.dashboard import render
from leakproof.dashboard.load import load_report
from leakproof.types import BatchReport, TriagedFinding

#: The four backend actions (design decision D8; ``gate/__init__.py``). The
#: wireframe's UNEXPLAINED "DISMISS" button and the CLAIM-READY/BLOCKED
#: "REJECT" button both post to "reject" -- ``AuditAction`` and the gate
#: module have no distinct "dismiss" action, so DISMISS is REJECT under a
#: label that fits the UNEXPLAINED gate (see report, Open questions).
_ACTIONS: dict[str, Any] = {
    "approve": gate.approve,
    "override": gate.override,
    "reject": gate.reject,
    "flag": gate.flag,
}

#: Placeholder audit timestamp. D18 bans reading the system clock outside
#: cli.py, and every gate action currently raises NotImplementedError before
#: this value would ever reach a written entry -- so it exists only to satisfy
#: the ``ts`` parameter shape, not to record a real time. Lane O should thread
#: a real clock (e.g. cli.py's ``now_iso``) through ``create_app`` when the
#: gate is wired for real, rather than reading it here.
PLACEHOLDER_TS = "1970-01-01T00:00:00+00:00"


def find_finding(report: BatchReport, finding_id: str) -> TriagedFinding | None:
    for item in report.queue:
        if item.finding.finding_id == finding_id:
            return item
    return None


def dispatch_gate_action(
    action: str,
    finding_id: str,
    report: BatchReport,
    log: AuditLog,
    out_dir: Path,
    *,
    actor: str = "dashboard",
    ts: str = PLACEHOLDER_TS,
) -> object:
    """Calls the matching ``leakproof.gate.*`` function. Framework-free, so it
    can be unit tested (including the ``NotImplementedError`` it currently
    always raises) without the ``serve`` extra installed.

    Raises ``ValueError`` for an unknown action, ``KeyError`` for an unknown
    ``finding_id``, and lets ``leakproof.gate``'s own ``NotImplementedError``
    propagate -- the FastAPI route translates that to HTTP 501.
    """
    fn = _ACTIONS.get(action)
    if fn is None:
        raise ValueError(f"unknown gate action: {action!r}")
    if find_finding(report, finding_id) is None:
        raise KeyError(f"unknown finding_id: {finding_id!r}")
    if action in ("approve", "override"):
        return fn(finding_id, report, log, out_dir, actor=actor, ts=ts, as_of=report.as_of)
    return fn(finding_id, report, log, actor=actor, ts=ts, as_of=report.as_of)


def create_app(report_path: Path):
    """Returns a ``fastapi.FastAPI`` app. Untyped return because FastAPI is
    imported lazily below, not at module scope."""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:
        raise ImportError(
            "leakproof.dashboard.serve requires the 'serve' extra: "
            "`uv sync --extra serve` (make verify never needs it, D16)."
        ) from exc

    # ``render``'s explicit mode="served" below is what actually decides gate
    # rendering (D16); stamping report.mode to match keeps the two from
    # silently disagreeing about which mode this in-memory report is being
    # shown in (finding 12) -- whatever mode the on-disk report claims for
    # itself, the live server is always the served path.
    report = replace(load_report(Path(report_path)), mode="served")
    app = FastAPI(title="LeakProof")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return render(report, mode="served")

    @app.post("/gate/{action}/{finding_id}")
    def gate_action(action: str, finding_id: str) -> JSONResponse:
        log = AuditLog(Path("out/audit.jsonl"))
        try:
            dispatch_gate_action(action, finding_id, report, log, Path("out/claims"))
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return JSONResponse({"ok": True})

    return app
