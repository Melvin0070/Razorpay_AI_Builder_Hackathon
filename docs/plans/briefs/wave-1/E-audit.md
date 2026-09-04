Lane E · Wave 1 · GitHub issue #8 · role `lp-build` (Sonnet, high effort) · worktree branch `lane/E-audit`

## Mission
Write the append-only, hash-chained audit log (D21) and its verifier. The
chain is recomputed on every verify, never byte-compared, so reruns under
D18's reproducibility guarantee stay green while any edit to an entry fails
at the exact sequence number. The log explains how each exception reached its
state (`state_before` / `state_after`), not merely that something happened.

## Governing sections (read first)
- Design doc: D21 (schema, hash rule, recompute), D8 (pack first, entry
  second; orphan packs detectable on chain verification), D18.
- ADR-0004 (`flag` action). SECURITY.md (tamper-evident, not tamper-proof).
- Strategy §3 (Wave 1, lane E), §4.

## Files you own
- `src/leakproof/audit/`
- `tests/audit/`

## Files you must not read
- None.

## Interfaces you consume (frozen)
- `types.AuditEntry`; `contract.AuditAction`, `State`, `Paise`.
- `leakproof.gates.GateResult` for the gate callable.
- The `AuditLog` class and `verify_chain` signatures in the stub.

## Deliverables
1. Storage: one JSON object per line (JSONL) at `AuditLog(path)`. Append
   writes one line, flushes, fsyncs. Never rewrites.
2. Canonical JSON: `json.dumps(obj, sort_keys=True, separators=(",", ":"),
   ensure_ascii=False)` over the entry with the `hash` field removed and
   enums/dates as their string values. Document it in the module docstring;
   lane O and the metrics harness must be able to reproduce it.
3. Hash: `sha256(canonical_json(entry − hash) + prev_hash)` hex. Genesis
   `prev_hash` is 64 zeros. `seq` starts at 1 and increments by one.
4. `append(...)` takes `ts` from the caller (ISO-8601 string; `cli.py` owns
   the clock) and returns the completed `AuditEntry`.
5. `entries()`, `head()`.
6. `verify_chain(path, artifacts_root=None) -> ChainVerification`: recomputes
   every hash, checks `prev_hash` linkage and `seq` monotonicity, reports the
   first bad `seq` and why. When `artifacts_root` is given, every entry with
   an `artifact_path` must exist under it (orphan-pack detection, D8).
7. `audit_chain_gate(path, artifacts_root) -> GateResult` callable for the
   integrator to register in `HARD_GATES`. An absent log file is a passing
   gate with detail "no audit log yet".

## Tests required (in `tests/audit/`)
- Append three entries; `verify_chain` ok; hashes differ; `prev_hash` links.
- Tamper test: change one character in entry 2 on disk → verification fails
  at `seq == 2` with a reason naming the hash mismatch.
- Reorder test: swap two lines → fails at the first out-of-order `seq`.
- Orphan-pack test: entry with `artifact_path` that does not exist → fails
  naming the path; existing path → ok.
- Recompute-not-compare test: two logs with identical entries but different
  `ts` both verify (proves the verifier does not compare bytes to a golden).
- Property test (hypothesis): any sequence of appended entries verifies.
- Idempotent open: reopening an existing log continues `seq` and `prev_hash`
  from the head.

## Exit criteria
`make lint` and `make verify` green. No new dependency. No system clock. No
float. Conventional Commits with scope `audit`. Do not push.

## Report format
1. Summary · 2. Files · 3. Tests · 4. Interface change requests ·
5. What broke and how you got out · 6. Open questions.
