# LeakProof: Demo Data Sheet & Judge Defense Guide
## Razorpay AI Buildathon 2026 · Verified Numbers, Cases, and Technical Defense

This document contains the verified data, exact order IDs, test results, and anticipated technical questions for the Razorpay AI Buildathon presentation.

---

### 1. Verified Demo Batch Figures (150 Orders, 4 Settlement Cycles)

| Metric | Verified Value | Ground-Truth / Benchmark Context |
| :--- | :--- | :--- |
| **Batch ID** | `demo` | Seeded synthetic batch (`src/leakproof/generator/`) |
| **Marketplace** | `amazon.in` | 24-column Amazon Settlement V2 layout |
| **As-Of Date** | `2026-08-21` | Evaluated across 4 weekly settlement cycles |
| **Total Orders** | **150** orders | 145 matched cleanly |
| **Strict Match Rate** | **96.7%** (`145 / 150`) | Exact order-ID join against exported order book |
| **Adjusted Match Rate** | **98.6%** (`145 / 147`) | Excludes 3 cross-cycle in-transit returns (D20) |
| **Seeded Error Recall** | **90.0%** (`18 / 20`) | 18 of 20 seeded errors caught across 6 classes |
| **Per-Class Recall** | Class 1 (Commission): **100%**<br>Class 2 (Closing Fee): **100%**<br>Class 5 (Weight Slabs): **88.9%**<br>Class 6 (Unrefunded Returns): **100%**<br>Class 7 (TCS Mismatch): **100%**<br>Class 8 (Unexplained): **50.0%** | Comprehensive detector coverage across fee types |
| **Rupee Agreement** | **100.0%** (₹0.00 discrepancy) | Zero math errors on all detected anomalies |
| **Precision** | **34.0%** | Honest ratio reflecting full candidate pool |
| **26-Case Frozen Holdout**| **14 / 26 (53.8%)** passed | Complex edge cases (leap days, boundary floors) reported separately |

---

### 2. The 4-State Rupee Partition Breakdown

| State | Amount (₹) | Exception Count | Description & Actionability |
| :--- | :--- | :--- | :--- |
| **CLAIM-READY** | **₹6,894.06** | 42 exceptions | 100% policy-eligible, evidence verified, deadline open. 1-click filing pack ready. |
| **BLOCKED** | **₹2,601.86** | 6 exceptions | Legitimate leakage held by a specific seller action (e.g. GST invoice upload). |
| **NOT-CLAIMABLE** | **₹942.17** | 2 exceptions | Disqualified by policy (Rule exclusion: ₹629.79; Window expired: ₹312.38). |
| **TAX-REVIEW** | **₹103.48** | 2 exceptions | Statutory TCS/TDS mismatch routed to Chartered Accountant review. |
| **UNEXPLAINED** | **₹102.00** | 1 exception | Deterministic flag for unrecognised deduction code (`code-unseen`). |
| **BELOW-MATERIALITY**| **₹0.00** | 0 rows | Sub-floor fee anomalies held outside active recovery queue. |
| **TOTAL IDENTIFIED** | **₹10,438.09** | 50 exceptions | Sum of Claim-Ready, Blocked, and Not-Claimable. |
| **TOTAL FLAGGED** | **₹10,643.57** | 53 exceptions | Grand total across all 4 partition buckets. |

---

### 3. Key Demo Highlight Cases (Drill-Down Guide)

#### Case A: Commission Overcharge (The Headline Claim-Ready Win)
- **Order ID**: `408-9606110-9190751`
- **Class**: Class 1 (`COMMISSION_OVERCHARGE`)
- **State**: `CLAIM-READY`
- **Amount**: **₹399.92**
- **Evidence Status**: All eligibility checks and evidence requirements satisfied.
- **Why it matters**: Demonstrates exact rate card lookup (v2026-03) and 1-click generation of the claim pack (claim letter + cited line CSV + recomputation CSV).

#### Case B: The "Honesty Beat" — BLOCKED on Missing Tax Invoice
- **Order ID**: `406-8033657-7010859`
- **Class**: Class 5 (`REFUND_NO_FEE_REVERSAL`)
- **State**: `BLOCKED`
- **Amount**: **₹272.79**
- **Reason**: `Tax invoice for the returned item`
- **Blocker Kind**: `BlockerKind.SELLER_ACTION`
- **Why it matters**: Proves the agent **refuses to file unverified claims**. Amazon SAFE-T policy requires the seller's tax invoice for physical returns. Filing without it causes claim rejection and account health penalties.

#### Case C: NOT-CLAIMABLE — Seller-Initiated Refund Exclusion
- **Order ID**: `405-2873519-1778984`
- **Class**: Class 5 (`REFUND_NO_FEE_REVERSAL`)
- **State**: `NOT-CLAIMABLE`
- **Amount**: **₹629.79**
- **Reason**: `seller-issued refunds are excluded from SAFE-T`
- **Not Claimable Reason**: `NotClaimableReason.RULE`
- **Why it matters**: Demonstrates deep policy understanding. If a seller voluntarily issues a refund to a buyer, Amazon policy disallows SAFE-T reimbursement. Flagging this saves finance teams from wasted dispute cycles.

#### Case D: NOT-CLAIMABLE — 60-Day Filing Window Expired
- **Order ID**: `403-2058316-1984458`
- **Class**: Class 5 (`REFUND_NO_FEE_REVERSAL`)
- **State**: `NOT-CLAIMABLE`
- **Amount**: **₹312.38**
- **Reason**: `filing window expired`
- **Not Claimable Reason**: `NotClaimableReason.WINDOW_EXPIRED`
- **Why it matters**: Demonstrates active deadline computation. Overcharges older than 60 days cannot be recovered on Amazon India.

#### Case E: UNEXPLAINED Deduction (Code Unseen)
- **Order ID**: `405-8523401-8834490`
- **Class**: Class 8 (`UNEXPLAINED_DEDUCTION`)
- **State**: `UNEXPLAINED`
- **Amount**: **₹102.00**
- **Reason**: `code-unseen`
- **Why it matters**: When the marketplace introduces an unknown fee code, the system flags it deterministically rather than guessing or dropping it.

---

### 4. Terminal Commands Cheat Sheet

```bash
# 1. Run full verification (911 tests + 3 hard gates, 100% offline, zero network)
make verify

# 2. Run code style and formatting checks
make lint

# 3. Generate the self-contained demo dashboard
make demo
# Emits out/demo.html -> Open in browser:
open out/demo.html

# 4. Print empirical accuracy metrics (recall, precision, rupee agreement, match rate)
make metrics

# 5. Live approval server (FastAPI)
make serve
```

---

### 5. Anticipated Judge Questions & Technical Defense

#### Q1: "How do you guarantee the LLM doesn't hallucinate numbers or cite the wrong amount?"
> **Defense (D2 Invariant)**:
> *"The LLM is architecturally barred from handling money. The prompt sent to the LLM contains zero rupee amounts—only line IDs and policy clauses. The LLM outputs structured claim prose using dynamic tokens like `{{amt:settlement_line_1204}}`. Our deterministic Python engine replaces those tokens with exact integer paisa amounts computed from versioned rate cards. An LLM cannot hallucinate a number it was never given and is not allowed to generate."*

#### Q2: "Why is your precision 34% if your recall is 90%?"
> **Defense (Honest Financial Accounting)**:
> *"In fraud and leakage recovery, precision measures how many total candidate anomalies flagged by the detectors proved to be genuine seeded errors. Our candidate pool captures subtle edge anomalies (like borderline weight slab differences). More importantly, our 4-state triage filters out unclaimable items, so the merchant only sees high-conviction claims in CLAIM-READY. We report our raw precision honestly rather than artificially filtering the candidate pool to inflate headline numbers."*

#### Q3: "Why did you split the match rate into Strict and Adjusted?"
> **Defense (D10 / E-commerce Reality)**:
> *"A strict match rate compares orders in the current cycle against settlements in the current cycle. But e-commerce has return lags: an order placed on August 5 might have a return processed on August 20. If you enforce strict 1-to-1 matching, in-transit returns artificially depress your match rate. Our Strict Match Rate is 96.7% (145/150). When adjusting for 3 in-transit return orders that span cycles (D20), our Adjusted Match Rate is 98.6%. We report both out loud because finance controllers need to see the cycle delta."*

#### Q4: "Why is TCS calculated at 0.5% when GST s.52(1) says up to 1%?"
> **Defense (ADR-0008 Compliance)**:
> *"Under Section 52(1) of the CGST Act, the statutory ceiling is 1% (0.5% CGST + 0.5% SGST). However, the CBIC notification sets the notified operative rate at 0.5% aggregate (0.25% CGST + 0.25% SGST). A naive system hardcoding the 1% statutory ceiling would trigger false tax mismatch anomalies on 100% of marketplace orders. We codified ADR-0008 to ensure our Class 7 detector tests against the real notified rate."*

#### Q5: "How does this integrate with Razorpay?"
> **Defense (Razorpay Synergy)**:
> *"Three direct touchpoints:*
> 1. **RazorpayX**: Embeds directly into RazorpayX current accounts as an automated marketplace reconciliation module, matching Amazon/Flipkart payouts against incoming bank UTRs.
> 2. **Razorpay Capital**: Enables real-time, verified underwriting. Razorpay Capital can instantly discount or advance cash against CLAIM-READY marketplace receivables with near-zero default risk.
> 3. **Magic Checkout / D2C**: Provides D2C merchants selling across Shopify and marketplaces with unified revenue assurance.*"
