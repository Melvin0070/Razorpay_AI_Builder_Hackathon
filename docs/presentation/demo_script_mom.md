# LeakProof: 5-Minute Pitch & Demo Script (MoM)
## Razorpay AI Buildathon 2026 · Video & Live Presentation Choreography

This document is the exact second-by-second script and visual choreography for your 5-minute hackathon pitch video or live judge evaluation. Follow the timestamps and action cues precisely.

---

### Timing Overview
| Segment | Timestamp | Screen View | Primary Goal |
| :--- | :--- | :--- | :--- |
| **Minute 1: The Problem** | 0:00 – 1:00 | Slides 1 & 2 + Settlement Raw TSV | Frame the ₹20,000 Cr margin leakage and why existing tools fail |
| **Minute 2: The Live Run** | 1:00 – 2:00 | Terminal (`make demo`) → Browser (`demo.html`) | Show keyless execution, strict vs adjusted match rate, 4 rupee lines |
| **Minute 3: Drill-Down** | 2:00 – 3:00 | Browser (`demo.html` Queue & Claim Pack Modal) | Source rows → Recomputation → SAFE-T LLM Draft → 1-Click Approve |
| **Minute 4: The Honesty Beat**| 3:00 – 4:00 | Browser (`demo.html` BLOCKED case) + Terminal | Show the agent refusing to file without GST invoice; show 26-case holdout |
| **Minute 5: Architecture & Fit**| 4:00 – 5:00 | Slide (Architecture) → Slide (RazorpayX Fit) | Hash chain audit trail, D2 invariant, Razorpay ecosystem synergy |

---

### Detailed Choreography

#### MINUTE 1: The Problem Framing (0:00 – 1:00)
**On Screen:**
- *0:00 – 0:20*: Slide 1 (Title: LeakProof — Deterministic Money, Probabilistic Language).
- *0:20 – 0:45*: Slide 2 (Friction Cards: 24-column TSV sheet, 2–5% GMV loss, 60-day deadline).
- *0:45 – 1:00*: Quick cut to a real 24-column marketplace settlement TSV with thousands of dense rows.

**Spoken Script:**
> *"Hi everyone, I'm Melvin. In Indian e-commerce, verification capacity—not generation speed—is the true bottleneck in financial operations.*
>
> *Every month, Indian D2C brands selling on Amazon and Flipkart process thousands of orders across dense 24-column settlement sheets. Between shifting referral fee slabs, closing fees, return logistics, and statutory TCS deductions, sellers lose 2% to 5% of their top-line revenue to silent settlement leakage.*
>
> *Worse, marketplaces enforce a strict 60-day deadline. If you don't catch an overcharge with cited evidence, that money is permanently gone.*
>
> *Incumbent tools try to solve this by dumping thousands of unverified alerts on finance teams—most of which are rejected by Amazon. Today, we built **LeakProof**: an autonomous marketplace auditor that proves what you can actually recover, and tells you exactly what blocks the rest.*
>
> *In direct compliance with Razorpay's Track 04 brief, our 150-order transaction batch is generated synthetically with 20 seeded ground-truth errors—protecting seller confidentiality while rigorously stress-testing edge cases. But critically, every fee slab, category commission, and SAFE-T policy we test against is 100% real, dated Amazon India policy."*

---

#### MINUTE 2: The Live Execution & Honest Partition (1:00 – 2:00)
**On Screen:**
- *1:00 – 1:15*: Clean Terminal window. Run commands:
  ```bash
  make demo
  make serve
  ```
  Highlight the output: `make demo` emits `out/demo.html` in **<150ms** as a self-contained, keyless compliance archive. `make serve` starts the live interactive controller on `http://127.0.0.1:8000`.
- *1:15 – 2:00*: Open browser at **`http://127.0.0.1:8000`**. Full-screen dashboard showing the top summary bar and metrics strip. Point your cursor to the Match Rate chip and the 4 Rupee cards.

**Spoken Script:**
> *"Let's see it live. In our terminal, I run `make demo`, which emits an offline compliance archive in under 150 milliseconds. Then I run `make serve` to start our live finance controller at `http://127.0.0.1:8000`.*
>
> *With zero external network calls and no API key required, LeakProof ingests 150 orders across 4 weekly settlement cycles, folds multi-cycle settlement lines, executes our detection suite, assesses filing evidence, and renders this live interactive controller.*
>
> *Notice our headline reconciliation rates: we report two distinct match rates out loud.*
> *Our **Strict Match Rate is 96.7%**—145 out of 150 orders matched cleanly.*
> *Our **Adjusted Match Rate is 98.6%**—because our ledger recognizes 3 in-transit return orders that span rolling weekly cycles, exactly as real commerce behaves.*
>
> *Now, look at our Rupee Partition. We do not cherry-pick a single vanity number. We partition the batch into four exhaustive states:*
> - *₹6,894.06 is **CLAIM-READY** across 42 orders—ready to file right now.*
> - *₹2,601.86 is **BLOCKED** across 6 orders—recoverable, but held on specific vendor actions.*
> - *₹942.17 is **NOT-CLAIMABLE** across 2 orders—dead by marketplace policy.*
> - *And ₹205.48 is in **TAX-REVIEW & UNEXPLAINED**.*
> *Every single paisa is accounted for."*

---

#### MINUTE 3: End-to-End Claim Drill-Down (2:00 – 3:00)
**On Screen:**
- *2:00 – 2:25*: On `http://127.0.0.1:8000`, click on **Order `408-9606110-9190751`** (Commission Overcharge, ₹399.92, `CLAIM-READY`). The right-hand detail pane displays:
  1. The cited settlement row (`settlement_2026-08-07.txt:189`).
  2. The Recomputation diff table: `expected → ₹849.83`, `difference → ₹399.92`.
  3. The category and policy basis: `amz-in-ref-2026-03-16-electronics-accessories-b3`.
  4. The LLM-drafted dispute prose: *"Commission was charged at a rate exceeding the published Amazon India schedule for category electronics-accessories. Recomputation is attached; requesting an adjustment of ₹399.92 to the referral fee."*
- *2:25 – 2:45*: Point your cursor to the live green **`APPROVE & QUEUE`** button. Read the consequence notice: *"Writes a claim pack and one audit entry. Nothing is filed. Approving twice is a no-op."*
- *2:45 – 3:00*: Click **`APPROVE & QUEUE`**!
  The button instantly updates to **"Done."** Switch briefly to terminal or run:
  ```bash
  ls out/claims && tail -n 1 out/audit.jsonl
  ```
  Show the written Claim Pack JSON and the SHA-256 cryptographic sequence #1 entry.

**Spoken Script:**
> *"Let's drill into a live claim: Order 408, a ₹399.92 commission overcharge on an electronics accessory.
>
> Here you see our core thesis in action: **deterministic money, probabilistic language**.
>
> On the left, the math is 100% deterministic. LeakProof loaded the dated Amazon Rate Card, verified the category fee bracket, and computed the exact discrepancy down to the paisa: ₹399.92. The LLM was never allowed to touch this number.
>
> On the right, the LLM generated the formal dispute narrative. Under our D2 architectural invariant, the prompt never received a rupee figure; the LLM outputted structured prose citing marketplace policies with dynamic line tokens like `{{amt:settlement_...}}`, and our engine deterministically resolved the verified amount into the template.
>
> Now, watch the human gate. When I click this green **APPROVE & QUEUE** button, the live FastAPI backend executes: it writes a complete, self-contained Claim Pack JSON into `out/claims/` and appends an immutable entry to our SHA-256 audit log. Approving twice is strictly idempotent—no duplicate files, no duplicate audit entries."*

---

#### MINUTE 4: The "Honesty Beat" & Held-Out Test Set (3:00 – 4:00)
**On Screen:**
- *3:00 – 3:30*: On `http://127.0.0.1:8000`, click the **`BLOCKED`** filter chip. Select Order `406-8033657-7010859` (₹272.79 Refund without Fee Reversal).
  Show that instead of a normal approve button, it renders **`DRAFT WITHOUT EVIDENCE`** and **`REJECT`**, with the warning: *"Drafts without: Tax invoice for the returned item. Pack marked OVERRIDDEN. Never enters ₹ claim-ready."*
- *3:30 – 3:45*: Click the **`NOT-CLAIMABLE`** chip. Select Order `405-2873519-1778984` (₹629.79). Show the button **`DRAFT DESPITE EXCLUSION`** and reason: *"Exclusion: Seller-Initiated Refund"*.
- *3:45 – 4:00*: Switch briefly to Terminal and run:
  ```bash
  make metrics
  ```
  Show the JSON metrics output with 90% recall, 100% rupee agreement, and the separate 26-case holdout line.

**Spoken Script:**
> *"Now for the most important moment in this presentation: the honesty beat.*
>
> *Look at Order 406. Amazon failed to reverse a ₹272.79 fee on a customer return. Every other tool on the market would blindly submit this claim. But LeakProof inspects the evidence supply, detects that the physical return lacks a seller GST invoice, and **refuses to mark it claim-ready**.*
>
> *Submitting a claim without a required tax invoice gets rejected and penalizes the seller's account health. We protect the merchant by blocking it and guiding them to upload the invoice.*
>
> *Look at Order 405: ₹629 was deducted, but because our engine detects that the seller initiated the return, Amazon's SAFE-T policy explicitly bars recovery. We mark it NOT-CLAIMABLE. We don't sell false hope.*
>
> *In our terminal, running `make metrics` proves our empirical rigor. Because our transaction batch is seeded with ground-truth errors while using real Amazon rate cards, we can prove our numbers with mathematical certainty: **90% recall**, **100% rupee agreement**, and our **26-case frozen holdout** reported completely honestly at 53.8% on its own line—never blended into marketing numbers."*

---

#### MINUTE 5: Architecture, Hash Chain, & Razorpay Strategic Fit (4:00 – 5:00)
**On Screen:**
- *4:00 – 4:25*: Slide 9 (Enterprise Security: SHA-256 Hash Chain `out/audit.jsonl` & 911 Offline Tests).
- *4:25 – 4:45*: Slide 10 (Razorpay Strategic Fit: RazorpayX Financial Ops + Razorpay Capital Claim Advance).
- *4:45 – 5:00*: Slide 12 (Conclusion & GitHub Repo Link).

**Spoken Script:**
> *"Under the hood, LeakProof is built for the CFO and compliance officer. Every single gate action—approvals, rejections, overrides—appends to a tamper-evident, SHA-256 hash-chained audit log. If a single byte is altered, our verification gate fails instantly. Our entire test suite of 911 tests passes in under 3.5 seconds completely offline.*
>
> *Finally, the strategic fit for Razorpay: Razorpay already leads merchant payments and banking with RazorpayX. By embedding LeakProof into RazorpayX, merchants get an autonomous finance controller that audits marketplace payouts against bank UTR credits.*
>
> *Even bigger: Razorpay Capital can use our verified, CLAIM-READY receivables to provide instant working-capital advances against pending marketplace claims, eliminating cash-flow wait times.*
>
> *In financial operations, trust is not built by generating answers faster; it is built by proving every single rupee beyond doubt. LeakProof is fully merged, tested, and ready. Thank you!"*

---

### Presentation Rehearsal Tips for the Video Recording
1. **Screen Layout**:
   - Left half: Terminal / VS Code.
   - Right half: Chrome Browser with `out/demo.html` open at 100% zoom.
2. **Terminal Preparation**:
   - Clear terminal before recording (`clear`).
   - Have commands pre-typed or in shell history:
     ```bash
     make verify
     make demo
     make metrics
     ```
3. **Pacing**:
   - Speak with calm, confident authority. Do not rush through the numbers—let the ₹6,894.06 and 96.7% match rate land clearly with the judges.
4. **The "Honesty Beat" Emphasis**:
   - When you show Order `406-8033657-7010859` (the BLOCKED GST invoice case), lean in: *this is what wins hackathons at fintech companies like Razorpay*, because it shows you understand financial risk and false-positive cost.
