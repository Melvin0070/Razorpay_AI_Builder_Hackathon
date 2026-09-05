# LeakProof: Pitch Deck Presentation
## Razorpay AI Buildathon 2026 · Track 04: AI Finance Controller & Track 03: AI Revenue Recovery

---

### Slide 1: Title & The Core Thesis
- **Slide Title**: **LeakProof**
- **Subtitle**: Deterministic Money, Probabilistic Language — Marketplace Settlement Auditor & Recovery Agent
- **Track**: Razorpay AI Buildathon · Track 04 (AI Finance Controller) / Track 03 (AI Revenue Recovery)
- **Presenter**: Melvin & Team
- **Visual Layout**:
  - Dark-mode background (`#0e0b08`) with Razorpay blue (`#0c2340` / `#3395ff`) accents.
  - Headline split-screen:
    - Left: *The Problem* — A chaotic 24-column marketplace settlement sheet with hundreds of unparsed deductions.
    - Right: *The Solution* — The LeakProof 4-State Rupee Partition (`CLAIM-READY`, `BLOCKED`, `NOT-CLAIMABLE`, `UNEXPLAINED`).
  - Trust Badge: *"911 Verified Tests · Zero Rupee Hallucination · Cryptographic Audit Trail"*.
- **On-Slide Bullets**:
  - Traditional tools claim: *"We found ₹1,00,000 in leakage!"* and drown finance teams in 70% unclaimable noise.
  - LeakProof delivers: **We tell you what you can actually recover, and exactly what blocks the rest.**
- **Speaker Notes (25 seconds)**:
  > "Hi everyone, I'm Melvin. In Indian e-commerce, verification capacity—not generation speed—is the true bottleneck in financial operations. Today, we're introducing LeakProof, an autonomous marketplace settlement auditor and claim-recovery agent built on an uncompromising architectural doctrine: Deterministic money, probabilistic language. We never let an LLM do arithmetic or invent numbers. We prove every single rupee from source rows, partition exceptions into actionable states, and generate filing-ready claim packs with complete human governance."

---

### Slide 2: The Problem — The ₹20,000 Cr Settlement Black Hole
- **Slide Title**: Where D2C Margins Go to Die
- **Subtitle**: Why Indian e-commerce sellers lose 2% to 5% of GMV in settlement friction
- **Visual Layout**:
  - Three visual friction cards:
    1. **Rate Card Chaos**: 15+ fee types (referral fees, closing fees, pick & pack, weight slabs, TCS, TDS) shifting across product categories and price tiers every quarter.
    2. **The Asymmetric Return**: When a customer returns an item, forward and reverse logistics are deducted, but referral fees are frequently unreversed.
    3. **Ops Bandwidth Paralysis**: Finance teams download 24-column TSV files with rolling 7-day cycles. Auditing 10,000 orders manually requires 60+ human hours every month.
  - Bottom Callout Banner: *"Marketplaces impose strict 60-day filing windows. If an overcharge is not claimed with full cited evidence before the deadline, that margin is permanently lost."*
- **On-Slide Data Callouts**:
  - **2%–5%**: Average GMV lost to uncontested settlement deductions.
  - **< 15%**: Proportion of legitimate leakage recovered by typical D2C sellers.
  - **60 Days**: Strict SAFE-T filing window on Amazon India before claims expire forever.
- **Speaker Notes (30 seconds)**:
  > "If you sell on Amazon India or Flipkart, you know that receiving your payout is only half the story. Between commission brackets, closing fee tiers, return logistics, and statutory TCS deductions, sellers lose 2 to 5 percent of their revenue to silent errors. When returns happen, fee reversals are frequently missed. But finance teams can't audit 24-column settlement sheets line-by-line. Worse, incumbent 'recovery software' dumps hundreds of false positives on merchant dashboards, wasting weeks chasing claims that marketplace policies explicitly forbid."

---

### Slide 3: The Architectural Breakthrough — "Deterministic Money, Probabilistic Language"
- **Slide Title**: The Core Doctrine
- **Subtitle**: Complete separation of financial computation from natural language reasoning
- **Visual Layout**:
  - Two-column architectural split:
    - **Left Column (Deterministic Engine - Pure Python / Math)**:
      - Ingestion with dirty-data quarantine (D7).
      - Exact order-keyed ledger fold & 4-point tiebreaking (D20).
      - Precise rate-card lookup with dated versions & category slabs.
      - 100% integer paisa arithmetic (`Paise = int`). Zero floating-point drift.
      - Tamper-evident, hash-chained audit log (SHA-256).
    - **Right Column (Probabilistic Engine - LLM / Reasoning)**:
      - Reads seller evidence companion files (invoices, courier PODs, damage photos).
      - Evaluates natural language policy rules (e.g. SAFE-T exclusions, courier guidelines).
      - Drafts formal marketplace claim filings.
      - **D2 Invariant**: The LLM prompt NEVER contains rupee amounts. The LLM only outputs structured prose with immutable line-ID tokens (`{{amt:line_id}}`). The engine resolves the exact paisa amount at render time.
- **On-Slide Callout**:
  - *"An LLM that hallucinates in marketing writes funny copy. An LLM that hallucinates in finance creates compliance liabilities and rejected claims."*
- **Speaker Notes (35 seconds)**:
  > "At LeakProof, our breakthrough is architectural: Deterministic money, probabilistic language. We enforce a strict firewall between math and text. All fee recomputations, ledger folding, and match rates are computed deterministically in integer paisa. The LLM is used exclusively where language models shine: classifying unstructured seller evidence, evaluating ambiguous policy clauses, and drafting professional dispute claims. Under our D2 invariant, the LLM prompt never sees rupee amounts, making hallucinated fee calculations mathematically impossible."

---

### Slide 4: The 4-State Rupee Partition (The Antidote to Cherry-Picking)
- **Slide Title**: Honest Triage: The 4-State Rupee Partition
- **Subtitle**: Every single paisa accounted for across an exhaustive mathematical precedence ladder
- **Visual Layout**:
  - Four distinct colored metric cards representing the live demo batch (150 orders):
    1. **CLAIM-READY (Green)**: **₹6,894.06** (42 exceptions)
       - *Definition*: 100% policy eligible, all evidence verified, filing window open. Ready for 1-click filing.
    2. **BLOCKED (Amber)**: **₹2,601.86** (6 exceptions)
       - *Definition*: Legitimate leakage detected, but held by a named dependency (e.g., GST invoice missing, courier POD pending).
    3. **NOT-CLAIMABLE (Red)**: **₹942.17** (2 exceptions)
       - *Definition*: Transparently disqualified by marketplace policy (Rule exclusion: ₹629.79; Filing window expired: ₹312.38).
    4. **TAX-REVIEW & UNEXPLAINED (Blue & Purple)**: **₹205.48** (3 exceptions)
       - *Definition*: TCS statutory discrepancy routed to CA review (₹103.48); Unseen marketplace deduction code flagged (₹102.00).
  - Bottom Rule: **Strict Match Rate: 96.7% | Adjusted Match Rate: 98.6%**.
- **Speaker Notes (40 seconds)**:
  > "In Razorpay's Track 04, the bar is explicit: 'Throughput plus measured accuracy plus an honest exception list. One cherry-picked match proves nothing.' LeakProof doesn't just produce a single aggregate leakage number. We pass every finding through an immutable 7-step precedence ladder that partitions every rupee into four exhaustive states. We show the merchant ₹6,894 ready to claim today, ₹2,601 blocked on specific seller actions, and critically, ₹942 that is dead because the filing window expired or policy excludes it. Telling a CFO what cannot be claimed is just as valuable as telling them what can."

---

### Slide 5: The End-to-End Pipeline
- **Slide Title**: Autonomous Finance Ops Pipeline
- **Subtitle**: From raw marketplace exports to tamper-evident claim packs
- **Visual Layout**:
  - Horizontal flowchart showing data transformation:
    1. **Ingest & Quarantine**: Orders CSV, V2 Settlement TSV, Bank Statement, Seller Profile, and Evidence Companion. Corrupt rows quarantined with line-specific diagnostic hints (D7).
    2. **Ledger Fold**: Multi-cycle cross-matching joins settlement cycles to orders with deterministic tiebreaks.
    3. **Detectors**: 6 specialized detectors evaluate Commission (Class 1), Closing Fee (Class 2), Weight Overcharges (Class 5), Unrefunded Returns (Class 6), TCS (Class 7), and Unexplained Codes (Class 8).
    4. **Evidence & Window Triage**: Computes active SAFE-T deadline timers and verifies required proof.
    5. **LLM Drafter**: Synthesizes formal claim prose citing exact Amazon Help Hub policy references.
    6. **Human Gate & Hash-Chained Audit**: Approvals emit structured claim packages (prose + source rows CSV + recomputation CSV) and append to a tamper-evident SHA-256 audit log.
- **Speaker Notes (35 seconds)**:
  > "Here is how data flows through LeakProof. We ingest standard settlement and order files. If an export has malformed headers or corrupt values, it is safely quarantined—never silently dropped. Our ledger folds multi-cycle settlement lines onto order records. Detectors cross-reference versioned rate cards. Our evidence engine checks filing deadlines down to the day. The LLM drafter generates the dispute narrative. Finally, the merchant reviews the exception in our dashboard, clicks approve, and our system outputs a complete claim pack while recording the action to an immutable, hash-chained audit log."

---

### Slide 6: Deep Dive — Anatomy of a Validated Claim
- **Slide Title**: From Settlement Line to Bank-Grade Claim Pack
- **Subtitle**: Live walkthrough of Order `408-9606110-9190751` (Commission Overcharge)
- **Visual Layout**:
  - 3-Panel Inspection Flow:
    - **Panel 1: Source Data**: Settlement Line `settlement_2026-08-07.txt:189` shows commission billed exceeding the published category fee schedule.
    - **Panel 2: Deterministic Recomputation**:
      - Category: Electronics Accessories (`ELEC-PWB-49`).
      - Rate-card lookup: rule `amz-in-ref-2026-03-16-electronics-accessories-b3`.
      - Expected Fee: ₹849.83.
      - Discrepancy identified: **₹399.92**. Exact paise: `39992`.
    - **Panel 3: Generated Claim Pack**:
      - Cited Lines CSV: Pins exact physical row in marketplace settlement file.
      - Recomputation CSV: Step-by-step mathematical proof.
      - Drafted Claim Prose: D2-verified template resolved to exact paise: *"Commission was charged at a rate exceeding the published Amazon India schedule for category electronics-accessories. Recomputation is attached; requesting an adjustment of ₹399.92 to the referral fee."*
      - Audit Proof: Cryptographic sequence `#1`, tamper-evident SHA-256 hash.
- **Speaker Notes (40 seconds)**:
  > "Let's examine a live claim in detail. For order 408, Amazon overcharged commission on an electronics accessory. LeakProof looked up the dated Amazon rate card rule for that category, computing an expected fee of ₹849.83 and an exact discrepancy of ₹399.92. On the right, the LLM drafted the formal dispute letter using dynamic placeholder tokens—without ever seeing a rupee numeral in the prompt. When the merchant clicks approve, LeakProof writes a complete, bank-grade Claim Pack to disk and logs an immutable SHA-256 audit entry. It is completely self-contained and audit-ready."

---

### Slide 7: The "Honesty Beat" — Why Refusing to Claim Wins Trust
- **Slide Title**: The Winning Differentiator: Bounded & Gated Execution
- **Subtitle**: Demonstrating graceful boundary handling and false-positive suppression
- **Visual Layout**:
  - Two contrasting real-world case studies from our demo batch:
    - **Case Study A: The BLOCKED Gate (Order `406-8033657-7010859`)**
      - *Issue*: ₹272.79 return fee uncredited.
      - *System Action*: **REFUSES to mark claim-ready**.
      - *Reason*: Amazon SAFE-T policy mandates a seller tax invoice for physical return claims.
      - *Merchant Action Required*: Uploads invoice -> Immediately unlocks claim.
    - **Case Study B: The NOT-CLAIMABLE Gate (Order `405-2873519-1778984`)**
      - *Issue*: ₹629.79 return fee without commission reversal.
      - *System Action*: **Marks NOT-CLAIMABLE (Rule Exclusion)**.
      - *Reason*: Order metadata reveals refund was initiated by the seller, not Amazon customer service. Amazon policy explicitly excludes seller-initiated refunds from SAFE-T reimbursement.
- **On-Slide Callout**:
  - *"In fintech, an agent that knows when to stop is infinitely more valuable than an agent that never stops."*
- **Speaker Notes (45 seconds)**:
  > "Here is what truly sets LeakProof apart, and what we call our 'honesty beat.' Look at order 406. It's a ₹272 return fee overcharge. Incumbent tools would blindly generate a claim. But LeakProof inspects the evidence supply, detects that the seller GST invoice is missing, and explicitly marks it BLOCKED. It refuses to file a doomed claim that would hurt the merchant's claim acceptance rate with Amazon. Look at order 405: ₹629 was deducted, but our engine sees that the refund was initiated by the seller, which Amazon's SAFE-T policy explicitly excludes. We mark it NOT-CLAIMABLE. This eliminates wasted finance ops hours and builds unbreakable credibility."

---

### Slide 8: Empirical Validation & The 26-Case Holdout
- **Slide Title**: Measured Performance, Not Marketing Claims
- **Subtitle**: Verified accuracy on seeded synthetic batches and held-out policy edge cases
- **Visual Layout**:
  - Top Metrics Grid:
    - **Seeded Recall**: **90.0%** (18 of 20 seeded errors caught across 6 classes)
    - **Per-Class Recall**: Commission: **100%** | Closing Fee: **100%** | TCS: **100%** | Unpaid Orders: **100%** | Weight Overcharges: **88.9%**
    - **Rupee Agreement**: **100.0%** (₹0.00 math error across all detected anomalies)
    - **Strict Match Rate**: **96.7%** (145/150 orders matched)
    - **Adjusted Match Rate**: **98.6%** (Accounting for in-transit return cycle lag)
  - Bottom Highlight Box (The Holdout Principle):
    - **26-Case Frozen Holdout**: **14 / 26 (53.8%) passed**.
    - *Integrity Note*: Authored by an independent lane; contains complex boundary conditions (leap year deadlines, obscure tax codes). Reported separately on its own line; **never blended into headline metrics to artificially inflate scores**.
- **Speaker Notes (40 seconds)**:
  > "In accordance with the Buildathon's mandate for measured accuracy, we rigorously evaluated LeakProof against seeded ground truth. On our 150-order benchmark batch, we achieve 90% overall recall, 100% recall on commission, closing fee, and tax anomalies, and 100% rupee agreement—zero paise of mathematical discrepancy. Furthermore, we test against a frozen 26-case holdout suite containing extreme policy edge cases like leap-day filing windows. We publish our holdout score of 53.8% transparently on its own line. We don't hide our edge-case boundaries; we engineer for them."

---

### Slide 9: Enterprise Security & Tamper-Evident Auditability
- **Slide Title**: Built for the CFO & Compliance Officer
- **Subtitle**: Cryptographic audit chains, deterministic gates, and zero-network CI
- **Visual Layout**:
  - Three Trust Pillars:
    1. **Tamper-Evident Hash Chain**: Every approval, rejection, override, and flag appends to an immutable JSONL log (`out/audit.jsonl`). Each entry hashes the previous entry's SHA-256 checksum. If a single byte or rupee amount is altered, `verify_chain()` immediately triggers a hard failure.
    2. **Human-in-the-Loop Governance**: Full role-based action logging (`approve`, `override`, `reject`, `flag`). Approvals are strictly idempotent—approving an exception twice produces zero duplicate claim files and zero duplicate log entries.
    3. **100% Offline CI Hard Gates**: 911 unit and property tests run in under 3.5 seconds. Zero external network calls, zero API key dependencies in test verification (`make verify`).
- **Speaker Notes (35 seconds)**:
  > "For financial controllers, auditability is non-negotiable. Every state transition in LeakProof is recorded in an append-only, SHA-256 hash-chained audit log. If an auditor modifies a single paisa or line ID, the chain verification immediately fails. Furthermore, all claim filings are strictly human-gated: our dashboard provides one-click approval with full drill-down. And for CI/CD reliability, our entire 911-test suite runs completely offline in 3 seconds, ensuring no flakiness or external API dependencies."

---

### Slide 10: Strategic Fit with Razorpay — The Next Frontier of RazorpayX
- **Slide Title**: Why LeakProof Belongs at Razorpay
- **Subtitle**: Completing the loop from payment collection to marketplace reconciliation
- **Visual Layout**:
  - Synergy Diagram linking LeakProof to 3 Razorpay Core Products:
    1. **RazorpayX Financial Operations**:
       - Today, RazorpayX automates vendor payouts, payroll, and tax deductions.
       - *With LeakProof*: RazorpayX becomes the definitive financial control center for D2C brands, automatically auditing marketplace settlements and reconciling incoming payouts against bank UTR credits.
    2. **Razorpay Capital & Instant Settlements**:
       - *The Opportunity*: Underwriting D2C brands usually requires static balance sheets.
       - *With LeakProof*: Razorpay Capital gets real-time, order-level visibility into verified, CLAIM-READY receivables. Razorpay can instantly factor or advance capital against pending marketplace claims at near-zero credit risk!
    3. **Razorpay Route (Split Payments)**:
       - Automated deduction matching for multi-vendor marketplaces, ensuring accurate commission and fee distributions.
- **Speaker Notes (40 seconds)**:
  > "Why is this the perfect product for Razorpay? Razorpay already owns payment collections via the Gateway and financial operations via RazorpayX. But for D2C brands, the single biggest headache after receiving payouts is marketplace reconciliation. By embedding LeakProof into RazorpayX, Razorpay provides merchants with an automated finance controller that catches fee leakages on Amazon and Flipkart. Even better: Razorpay Capital can use our verified CLAIM-READY receivables to provide instant working capital advances to merchants, creating an unbeatable flywheel."

---

### Slide 11: The Descope Ladder — Engineering Discipline
- **Slide Title**: The Descope Ladder: What We Cut & Why
- **Subtitle**: Demonstrating product focus, honesty, and pragmatic technical trade-offs
- **Visual Layout**:
  - Table of Deliberate Cuts:
    - **Cut 1: Flipkart & Meesho Parsers** -> *Why*: Prioritized 100% deep compliance with the Amazon V2 24-column settlement specification rather than shallow, brittle parsers across multiple marketplaces.
    - **Cut 2: Volumetric Weight Estimation** -> *Why*: Calculating box dimensions without warehouse 3D-scan data leads to disputed claims. We strictly audited weight handling against declared catalog weight slabs.
    - **Cut 3: Fuzzy Order Matching** -> *Why*: Fuzzy matching in financial reconciliation produces catastrophic false joins. We enforced exact order-id joins and isolated bank UTR reconciliation into a separate D6 reporting leg.
- **Speaker Notes (30 seconds)**:
  > "Great engineering is as much about what you choose not to build as what you build. We intentionally cut multi-marketplace support to master the complex Amazon V2 settlement format with complete accuracy. We cut volumetric weight guessing because filing claims on estimated dimensions gets seller accounts flagged. And we rejected fuzzy matching in favor of deterministic joins. This discipline allowed us to deliver a production-grade, hardened engine rather than a fragile hackathon proof-of-concept."

---

### Slide 12: Roadmap & Conclusion
- **Slide Title**: The Future of Autonomous Finance Ops
- **Subtitle**: LeakProof — Turning lost settlement margins into cash flow
- **Visual Layout**:
  - Roadmap Horizon (3 Phases):
    - **Q1 2026**: Amazon SP-API & Flipkart EDI direct connector; automated claim status webhook polling.
    - **Q2 2026**: Deep RazorpayX integration — automatic credit matching against Razorpay Current Accounts.
    - **Q3 2026**: Razorpay Capital 'ClaimAdvance' — instant 24-hour discounting on verified claim packs.
  - Big Concluding Quote:
    - *"In finance operations, trust is not built by generating answers faster; it is built by proving every single rupee beyond doubt."*
  - Links & Quick Start:
    - GitHub: `github.com/Melvin0070/Razorpay_AI_Builder_Hackathon`
    - Quick Run: `make demo` (self-contained HTML) · `make verify` (911 tests)
- **Speaker Notes (30 seconds)**:
  > "To conclude: LeakProof demonstrates that autonomous agents can solve real, high-stakes financial operations problems when paired with deterministic safeguards. We recover lost margins for Indian merchants, eliminate false alarms, and bridge seamlessly into the Razorpay financial ecosystem. All code is committed, tested across 911 test cases, and ready for demo today. Thank you, and I look forward to your questions!"

---
