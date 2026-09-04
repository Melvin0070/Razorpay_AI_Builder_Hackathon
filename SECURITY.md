# Security notes

- **No secrets in the tree.** The only credential this project ever uses is
  `ANTHROPIC_API_KEY`, read from the environment by `make triage` alone. It is
  never written to disk, never logged, and never needed by `make verify`,
  `make demo` or CI. `.env` is gitignored.
- **Zero network on the verify path.** Every hard gate and every published
  metric reproduces offline.
- **No system clock in money paths.** All window arithmetic takes an explicit
  `as_of`; only `cli.py` may read the clock, and a test enforces it.
- **Audit log is tamper-evident, not tamper-proof.** Entries are hash-chained
  and the chain is recomputed on every verify; anyone with write access to the
  file can rewrite history and re-chain it. Do not describe it as immutable.
- **Claim packs are written under a fixed output directory** from ids that are
  validated against the report before any path is formed.
- **Nothing is filed automatically.** Approve produces files on disk; there is
  no outbound integration to any marketplace.

Report a concern by opening an issue labelled `security`.
