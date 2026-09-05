"""Inline CSS, lifted from
``docs/designs/leakproof-exception-review-wireframe.html`` (D16: no external
resources of any kind). Selectors and CSS variables are unchanged from the
wireframe; additions needed to turn a static illustration into a working page
(row/pane show-hide, gate-result feedback) are marked below.
"""

from __future__ import annotations

CSS: str = """
  :root {
    --ink:       #1a1a1a;   /* primary text, solid fills            */
    --ink-2:     #444;      /* secondary text                       */
    --ink-3:     #595959;   /* tertiary — 7.0:1 on white (was #888) */
    --ink-label: #666;      /* uppercase labels — 5.3:1 on --bg-2   */
    --rule:      #ccc;      /* structural borders                   */
    --rule-2:    #e4e4e4;   /* hairlines between rows               */
    --bg:        #fff;
    --bg-2:      #f7f7f7;   /* header rows, section headers         */
    --bg-3:      #fafafa;   /* page ground, quoted claim text       */
    --sel:       #f0f0f0;   /* selected row                         */
    --hatch:      repeating-linear-gradient(-45deg,
                    var(--bg) 0 6px, #e0e0e0 6px 7.5px);
    --hatch-fine: repeating-linear-gradient(-45deg,
                    var(--bg) 0 2.5px, #c4c4c4 2.5px 4px);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
         background: var(--bg-3); color: var(--ink); padding: 16px;
         max-width: 1280px; margin: 0 auto; }
  .amt, .mono, .v, .ddl, .num {
    font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1;
    font-family: "SF Mono", Menlo, Consolas, monospace;
  }
  .frame { border: 1px solid var(--rule); background: var(--bg); margin-bottom: 22px; }
  header { display: flex; justify-content: space-between; align-items: baseline;
           padding: 12px 16px; border-bottom: 1px solid var(--rule); }
  header h1 { font-size: 15px; font-weight: 700; letter-spacing: .3px; }
  header .batch { font-size: 11px; color: var(--ink-3); }

  /* ── TIER 1-4 metrics ─────────────────────────────────────────────── */
  .metrics { padding: 14px 16px 12px; border-bottom: 1px solid var(--rule); }
  .t1 { display: flex; align-items: baseline; justify-content: space-between; }
  .t1 .k { font-size: 11px; text-transform: uppercase; letter-spacing: .7px; color: var(--ink-label); }
  .t1 .v { font-size: 30px; font-weight: 700; letter-spacing: -.5px; }

  .bar { display: flex; height: 22px; margin: 8px 0 6px; border: 1px solid var(--ink); }
  .bar span { display: block; }
  .bar .s-ready  { background: var(--ink); }
  .bar .s-block  { background: var(--hatch); border-left: 1px solid var(--ink); }
  .bar .s-noclaim{ background: var(--bg);  border-left: 1px solid var(--ink); }
  .legend { display: flex; gap: 26px; font-size: 12px; flex-wrap: wrap; }
  .legend .lab { color: var(--ink-label); text-transform: uppercase;
                 font-size: 10px; letter-spacing: .6px; }
  .legend .amt { font-weight: 700; font-size: 15px; }
  .legend .sub { font-size: 11px; color: var(--ink-3); margin-top: 1px; }

  .t3 { display: flex; gap: 26px; margin-top: 11px; padding-top: 9px;
        border-top: 1px solid var(--rule-2); font-size: 12px; flex-wrap: wrap; }
  .t3 .lab { color: var(--ink-label); text-transform: uppercase;
             font-size: 10px; letter-spacing: .6px; }
  .t3 .amt { font-weight: 700; }

  .t4 { margin-top: 9px; padding-top: 8px; border-top: 1px solid var(--rule-2);
        font-size: 11.5px; color: var(--ink-2); display: flex;
        justify-content: space-between; flex-wrap: wrap; gap: 6px; }
  .t4 b { color: var(--ink); }

  .cols { display: flex; }

  /* ── Exception queue ──────────────────────────────────────────────── */
  .list { flex: 1.55; border-right: 1px solid var(--rule); }
  .list .filters { display: flex; gap: 8px; padding: 9px 12px;
                   border-bottom: 1px solid var(--rule-2); font-size: 11.5px;
                   color: var(--ink-2); align-items: center; flex-wrap: wrap; }
  .chipf { border: 1px solid var(--rule); border-radius: 10px; padding: 2px 9px;
           background: var(--bg-2); cursor: pointer; font: inherit; color: inherit; }
  .chipf.on { background: var(--ink); color: var(--bg); border-color: var(--ink); }
  table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  th { text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: .5px;
       color: var(--ink-label); padding: 7px 10px;
       border-bottom: 1px solid var(--rule); background: var(--bg-2); }
  td { padding: 8px 10px; border-bottom: 1px solid var(--rule-2); vertical-align: top; }
  tr.row { cursor: pointer; }
  tr.sel td { background: var(--sel); }
  .amt { text-align: right; font-weight: 600; }
  .ddl { font-size: 11.5px; color: var(--ink-2); }
  .ddl b { color: var(--ink); }
  .grp { font-size: 10px; text-transform: uppercase; letter-spacing: .7px;
         color: var(--ink-label); background: var(--bg-2); padding: 5px 10px;
         border-bottom: 1px solid var(--rule-2); }

  /* ── FOUR STATES, FOUR FILLS. All full contrast. No strikethrough. ── */
  .st { display: inline-block; font-size: 12px; font-weight: 700; letter-spacing: .3px;
        padding: 3px 8px; border: 1px solid var(--ink); color: var(--ink); }
  .st.ready   { background: var(--ink); color: var(--bg); }
  .st.blocked { background: var(--hatch-fine); }
  .st.unexp   { background: var(--bg); border-style: dotted; }
  .st.noclaim { background: var(--bg); }
  .why { display: block; font-size: 11px; color: var(--ink-2); margin-top: 3px; }

  /* ── Detail pane ──────────────────────────────────────────────────── */
  .detail { flex: 1; padding: 13px 15px; font-size: 12.5px; }
  .detail h2 { font-size: 13px; margin-bottom: 2px; }
  .detail .sub { font-size: 11.5px; color: var(--ink-3); margin-bottom: 11px; }
  .sec { border: 1px solid var(--rule-2); margin-bottom: 10px; }
  .sec .h { font-size: 10px; text-transform: uppercase; letter-spacing: .6px;
            color: var(--ink-label); padding: 5px 8px; background: var(--bg-2);
            border-bottom: 1px solid var(--rule-2); }
  .sec .b { padding: 9px; }
  .cite { font-size: 11px; color: var(--ink-2); padding: 2px 0;
          font-family: "SF Mono", Menlo, Consolas, monospace;
          font-variant-numeric: tabular-nums; }
  .cite b { color: var(--ink); }
  .diff { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 11.5px;
          font-variant-numeric: tabular-nums; }
  .diff .neg { color: var(--ink-3); }
  .diff .row { padding: 1px 0; }
  .diff .note { color: var(--ink-3); font-family: -apple-system, sans-serif; }
  .evreq { font-size: 11.5px; padding: 2px 0; }
  .evreq .ok::before  { content: "\\2611  "; }
  .evreq .miss::before{ content: "\\2610  "; }
  .evreq .miss { font-weight: 700; }
  .unver, .pend { font-size: 10px; text-transform: uppercase; letter-spacing: .5px;
           border: 1px dotted var(--ink-2); color: var(--ink-2); padding: 1px 5px;
           margin-left: 5px; }
  .claim { font-size: 11.5px; color: var(--ink-2); background: var(--bg-3);
           border: 1px dashed var(--rule); padding: 8px; }
  a.cite-link { color: var(--ink-2); }

  /* ── Gate: one primary per state ──────────────────────────────────── */
  .gate { margin-top: 11px; padding-top: 10px; border-top: 1px solid var(--rule); }
  .btns { display: flex; gap: 8px; align-items: center; }
  .btn { border: 1.5px solid var(--ink); padding: 7px 15px; font-size: 12px;
         font-weight: 700; background: var(--bg); color: var(--ink);
         font-family: inherit; cursor: pointer; }
  .btn.pri  { background: var(--ink); color: var(--bg); }
  .btn.over { background: var(--hatch-fine); }
  .btn.flag { background: var(--bg); }
  .conseq { font-size: 12px; color: var(--ink-2); margin-top: 8px; line-height: 1.45; }
  .conseq b { color: var(--ink); }
  .gateresult { font-size: 12px; color: var(--ink-2); margin-top: 8px; }

  /* Static-export variant: the result, not a dead button. */
  .approved { border: 1px solid var(--ink); margin-top: 11px; }
  .approved .h { font-size: 10px; text-transform: uppercase; letter-spacing: .6px;
                 background: var(--ink); color: var(--bg); padding: 5px 9px; }
  .approved .b { padding: 9px; font-size: 11.5px; }
  .approved .row { display: flex; gap: 10px; padding: 3px 0; }
  .approved .row .k { color: var(--ink-label); width: 118px; flex: none;
                      text-transform: uppercase; font-size: 10px; letter-spacing: .5px;
                      padding-top: 2px; }
  .staticnote { font-size: 12px; color: var(--ink-2); margin-top: 11px;
                padding-top: 10px; border-top: 1px solid var(--rule); line-height: 1.5; }
  .staticnote code { background: var(--bg-2); padding: 1px 5px; border: 1px solid var(--rule-2); }

  /* Boundary states (frame 4): reuse of the metrics-tier classes inside a box. */
  .emptybox { border: 1px solid var(--rule-2); padding: 11px; margin-top: 6px; }
  .emptybox .headline { margin-top: 12px; padding-top: 11px;
                         border-top: 1px solid var(--rule-2); font-size: 13px; }

  /* Additions beyond the wireframe illustration, needed for a working page:
     row selection / filtering are plain show-hide, no animation. */
  [hidden] { display: none !important; }
  tr.row[hidden], .grp[hidden] { display: none !important; }
"""
