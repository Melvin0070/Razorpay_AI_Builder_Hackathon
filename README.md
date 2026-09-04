# LeakProof

Marketplace settlement leakage auditor and claim-recovery agent.
Razorpay AI Buildathon, Track 04 (AI Finance Controller).

[![ci](https://github.com/Melvin0070/Razorpay_AI_Builder_Hackathon/actions/workflows/ci.yml/badge.svg)](https://github.com/Melvin0070/Razorpay_AI_Builder_Hackathon/actions/workflows/ci.yml)

**Deterministic money, probabilistic language.** The LLM parses, explains,
classifies prose and drafts. It never computes a rupee amount and never files
anything. Every number traces to a source row. Every action lands in an
append-only, hash-chained audit trail. Every claim is human-approved.

Not "we find leakage" but: **we tell you what you can actually recover, and
exactly what blocks the rest.** Every exception lands in one of four computed
states, CLAIM-READY, BLOCKED (named blocker), NOT-CLAIMABLE (named rule), or
UNEXPLAINED (deterministic basis), and the rupees are partitioned accordingly.

## Status

Wave 0 of 5: foundation. The seams every module is coded against are frozen
(`src/leakproof/contract.py`, `types.py`, `scenarios.py`); the pipeline is
stubs. Progress by lane: [issues](https://github.com/Melvin0070/Razorpay_AI_Builder_Hackathon/issues),
one per lane, one milestone per wave. How it is being built:
[docs/plans/agent-team-build-strategy.md](docs/plans/agent-team-build-strategy.md).
What broke along the way: [docs/build-log.md](docs/build-log.md).

## Run

Requires [uv](https://docs.astral.sh/uv/). Python 3.12 is pinned and installed
by uv on first use.

```bash
make verify     # deterministic: every hard gate, zero network, no API key
make demo       # emits out/demo.html, self-contained, keyless   (lane G)
make serve      # FastAPI, only for the live approve interaction  (lanes G, O)
make triage     # opt-in LLM job; needs ANTHROPIC_API_KEY         (lane M)
make lint       # ruff
```

## Design

- [Design doc](docs/designs/leakproof-evidence-completeness.md), approved,
  revised 2026-09-04. Decisions are numbered D1–D23 and cited from code.
- [Wireframe](docs/designs/leakproof-exception-review-wireframe.html), the
  dashboard's starting markup.
- [ADRs](docs/adr/) for build-time decisions.
- [Amazon V2 settlement spec](docs/specs/amazon-settlement-v2.md) as read and
  written here, with per-row verification status.

## Limitations

Stated verbatim from the design doc; measured results are published whether or
not they meet the stated targets.

- "₹ recovered" is really "₹ identified + claim-ready." Actual recovery depends
  on marketplace adjudication; filing is human-gated by design. Do not
  overclaim.
- Rate cards drift. Fees are versioned config, clearly dated; a production
  system would sync them continuously.
- Synthetic realism has limits. Real reports contain pathologies no generator
  anticipates. All published accuracy figures are measured against seeded
  synthetic data, and no real seller data was used at any point.
- Eligibility rules marked `verified: false` were encoded from secondary
  sources with dates; treat their outputs accordingly.
- Ground-truth independence is real for fee arithmetic and weaker for
  eligibility: the manifest labels and the eligibility rules are two readings
  of the same login-walled policy text by the same person.
- Hash-chained audit log is tamper-evident, not tamper-proof.
- Accuracy targets are stated targets, not gates. Measured results are
  published whether or not they meet them.

## Licence

MIT. See [LICENSE](LICENSE).
