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

##### MINUTE 1: The Problem Framing (0:00 – 1:00)
**On Screen:**
- *0:00 – 0:20*: Slide 1 (Title: LeakProof — Deterministic Money, Probabilistic Language).
- *0:20 – 0:45*: Slide 2 (Friction Cards: 24-column TSV sheet, 2–5% GMV loss, 60-day deadline).
- *0:45 – 1:00*: Quick cut to a real 24-column marketplace settlement TSV with thousands of dense rows.

**Spoken Script:**
> *"Hi everyone, I'm Melvin. If you talk to any Indian D2C brand selling on Amazon or Flipkart, they'll tell you their biggest headache isn't making sales—it's getting paid correctly.
>
> Every week, marketplaces dump dense 24-column settlement reports with thousands of rows. Between changing category commissions, closing fees, return charges, and statutory tax deductions, brands silently bleed 2% to 5% of their revenue. That’s a ₹20,000 Crore margin leakage across Indian e-commerce every single year.
>
> Worse, marketplaces enforce an aggressive 60-day deadline. If a finance team doesn't catch an overcharge with documented proof in 60 days, that money vanishes forever.
>
> Most AI tools today try to solve this by spamming finance teams with hundreds of hallucinated alerts that Amazon immediately rejects.
>
> We built **LeakProof**: an autonomous finance controller for Indian marketplace sellers. It doesn't just spot fee leakage—it mathematically proves what you can recover, tells you exactly what blocks the rest, and drafts bank-grade dispute packages ready to file.
>
> To evaluate this rigorously without exposing private seller data, our demo runs on a 150-order benchmark batch with 20 seeded ground-truth errors. But every single fee schedule, commission slab, and reimbursement policy we test against is 100% real, dated Amazon India policy."*

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
> *"Let's see it in action.
>
> In our terminal, I run `make demo` and `make serve`. In under 150 milliseconds—completely offline, with zero external network calls—LeakProof ingests 150 orders across four weekly settlement cycles, reconciles payouts against bank credits, tests for fee overcharges, and spins up this live finance controller at localhost:8000.
>
> Look at our top metrics bar. First, our reconciliation rates.
>
> We report two numbers honestly: our **Strict Match Rate is 96.7%**—145 out of 150 orders reconciled cleanly. Our **Adjusted Match Rate is 98.6%**—because in real-world commerce, return shipments take time to cross weekly cycles, and our ledger recognizes those 3 in-transit orders rather than falsely flagging them as lost.
>
> Next, look at our Rupee Partition. Most tools give you a giant, misleading 'total leakage' number. We don't do that. We give the CFO four crisp, actionable buckets:
> - **₹6,894.06 is CLAIM-READY** across 42 orders. This is verified cash ready to recover right now.
> - **₹2,601.86 is BLOCKED** across 6 orders. This money is recoverable, but waiting on a specific document like a seller GST invoice.
> - **₹942.17 is NOT-CLAIMABLE**. Amazon policy explicitly bars recovery here—we tell the merchant immediately so they don't waste time.
> - And **₹205.48 is in TAX-REVIEW & UNEXPLAINED**.
>
> Every single paisa is accounted for down to the ledger."*

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
  The button instantly updates to **"Done."**

**Spoken Script:**
> *"Now let’s drill into a live claim: Order 408.
>
> On this electronics accessory, Amazon charged an inflated 12% referral commission. LeakProof caught it, pulled the published Amazon India rate card for electronics, and calculated the exact discrepancy down to the paisa: ₹399.92.
>
> This demonstrates our core architectural principle: **never let an LLM do math**.
>
> When AI tools ask ChatGPT or Claude to compute percentages across tax slabs, they hallucinate numbers and file rejected claims. In LeakProof, our math is 100% deterministic—the LLM was never allowed to touch this ₹399.92 figure.
>
> Instead, the LLM does what language models excel at: drafting the persuasive dispute letter. It cited Amazon India Fee Policy for electronics accessories, structured the formal legal narrative, and our engine safely injected the verified mathematical amount into the text.
>
> Now, watch the human gate. When I click this green **APPROVE & QUEUE** button... it's done.
>
> The live backend instantly wrote a complete, bank-grade Claim Pack to disk—including the dispute letter, the cited settlement row, and the mathematical proof—and committed a tamper-evident entry to our SHA-256 audit ledger.
>
> Clicking it again is completely idempotent. No duplicate claims, no duplicate files."*

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
  Show the JSON metrics output with 90% recall, 100% rupee agreement, and 96.7% match rate.

**Spoken Script:**
> *"Now for the most important part of this demo: what we call our **honesty beat**.
>
> In the queue, let's filter by **BLOCKED** and look at Order 406. Amazon failed to reverse a ₹272.79 fee on a customer return. Almost every other software tool would blindly file a claim.
>
> But LeakProof checks Amazon's evidence policy, detects that the seller GST tax invoice is missing, and **refuses to mark it claim-ready**.
>
> Why? Because filing a reimbursement claim without a tax invoice gets rejected by Amazon support and hurts the seller's account health. Instead of filing a doomed claim, LeakProof guides the seller: upload the invoice, and it unlocks instantly.
>
> Now look at Order 405 under **NOT-CLAIMABLE**: ₹629 was deducted, but our engine recognizes that the refund was initiated by the seller themselves. Amazon's SAFE-T policy explicitly excludes seller-initiated refunds from recovery. We mark it NOT-CLAIMABLE. We don't sell false hope.
>
> Finally, switching to our terminal and running `make metrics` proves our rigor. On our 150-order benchmark batch, we achieve **90% overall recall**, and **100% rupee agreement**—meaning across all detected claims, there is zero paise of mathematical error. Everything matches ground truth."*

---

#### MINUTE 5: Architecture, Hash Chain, & Razorpay Strategic Fit (4:00 – 5:00)
**On Screen:**
- *4:00 – 4:25*: Slide 9 (Enterprise Security: SHA-256 Hash Chain `out/audit.jsonl` & 916 Offline Tests).
- *4:25 – 4:45*: Slide 10 (Razorpay Strategic Fit: RazorpayX Financial Ops + Razorpay Capital Claim Advance).
- *4:45 – 5:00*: Slide 12 (Conclusion & GitHub Repo Link).

**Spoken Script:**
> *"Under the hood, LeakProof isn't just an AI script—it’s enterprise financial infrastructure.
>
> Every time a human reviews or approves a claim, the event is appended to an immutable, SHA-256 hash-chained audit log. If anyone tampers with a single number on disk, our verification gate fails immediately. Our entire suite of 916 automated tests runs in under 4 seconds, completely offline.
>
> Now, why does this belong at Razorpay?
>
> Razorpay already powers payments and banking for thousands of Indian D2C merchants through **RazorpayX**. By embedding LeakProof directly into RazorpayX, merchants get an autonomous finance controller that audits marketplace payouts against actual bank UTR credits automatically.
>
> But the biggest opportunity is **Razorpay Capital**. Right now, when a seller submits a ₹50,000 claim to Amazon, they wait 30 to 60 days to get paid.
>
> Because LeakProof provides mathematically verified, bank-grade claim packs, Razorpay Capital can underwrite and **instantly advance cash against verified claim-ready receivables**—giving merchants immediate working capital while Razorpay collects from the marketplace payout.
>
> In finance, trust isn't built by generating text faster; it's built by proving every single rupee beyond doubt. LeakProof is fully built, tested, and ready to deploy.
>
> Thank you!"*

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
