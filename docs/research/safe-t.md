# Research: Amazon India SAFE-T sources and claim examples

Lane RS2, Wave 0. Researched and written 2026-09-04 using the `browse` skill
(headless Chromium) for every page fetch; WebSearch was used only to discover
candidate URLs, never as a source of fact in its own right. "As of" below means
the date this lane accessed and read the page, unless the page carries its own
byline/update date, which is recorded separately.

**What this file is not.** Per the D12 independence wall (design doc §D12,
`docs/plans/agent-team-build-strategy.md` §1 and §3), this file does not state
what the filing window is, what is excluded, or what evidence is required. Lane F
(claimability labels) and Lane K (eligibility + evidence + deadlines) each read
the primary sources below independently and encode their own rule text from them.
Where the research below surfaces a *contradiction between secondary sources* on
a specific number, that contradiction is reported as a fact about the source
landscape (so F and K know to expect disagreement and to prefer primary sources),
not as a resolution of what the number is.

**Region-scoping caveat, found during this research and worth reading first.**
`sellercentral.amazon.in` hosts a shared global forum platform. A URL on that
domain is not proof the *content* is India-specific: several threads found via
search carry a "Country changed" banner and dollar amounts, meaning the visible
content is a US Seller Central thread, not an India one, despite the `.in` host.
The only reliable disambiguators found: presence of a "Country changed to United
States" banner, currency symbol (₹ vs $), and India-only vocabulary (Easy Ship,
Self-Ship, Seller Flex, GST). Every source below is labeled India-confirmed or
flagged otherwise.

---

## 1. Source list

### 1a. Primary — Amazon-authored

| URL | As of | Login-walled | Covers |
|---|---|---|---|
| `https://www.amazon.in/gp/help/customer/display.html?nodeId=GQ37ZCNECJKTFYQV` ("What is the A-to-z Guarantee?") | 2026-09-04 (page carries no byline date) | No — public, read without any account | A-to-Z Guarantee overview: what it protects, buyer eligibility conditions, buyer-side filing timeline (90 days from EDD via self-service), claim-status lookup, FAQ on refund-request limits |
| `https://www.amazon.in/gp/help/customer/display.html?nodeId=G9VEMT3X4FQET5DH` ("Appeal a Denied A-to-Z Guarantee Refund") | 2026-09-04 | No — public | The buyer-side appeal path after Amazon denies an A-to-Z refund request: what evidence to compile, the appeal window (stated on this page as 30 calendar days from the denial notice), Amazon's own response-time commitment |
| `https://www.amazon.in/gp/help/customer/display.html?nodeId=GSZAYH7K2C2NVNC9` ("Request an A-to-Z Guarantee Refund") | 2026-09-04 | Unconfirmed — URL confirmed via on-page navigation link from the overview page; body text not independently read this session | Title indicates: how a buyer files the original A-to-Z refund request |
| `https://www.amazon.in/gp/help/customer/display.html?nodeId=TwTcf5IuD4JWnKs4fY` ("Update or Upload Files to an A-to-Z Guarantee Refund") | 2026-09-04 | Unconfirmed — URL confirmed via navigation link only, body not read | Title indicates: evidence-file upload mechanics for an A-to-Z claim — likely relevant to Lane K's evidence-source-type modeling, unread |
| `https://www.amazon.in/gp/help/customer/display.html?nodeId=GX8W2A9JG23YBY9W` ("View the Request Status of an A-to-z Refund") | 2026-09-04 | Unconfirmed — URL confirmed via navigation link only, body not read | Title indicates: claim-status states a buyer can see |
| `https://www.amazon.in/gp/help/customer/display.html?nodeId=G4NEXG4WJ85JDFJG` ("Cancel or Reverse an A-to-Z Guarantee Refund") | 2026-09-04 | Unconfirmed — URL confirmed via navigation link only, body not read | Title indicates: how a granted A-to-Z refund can be reversed — relevant to the design's `C5_REVERSED_LATER_CYCLE` true-negative scenario |
| `https://sell.amazon.in/seller-blog/here-is-how-easy-ship-sellers-can-file-safe-t-claims` ("SAFE-T claims — Here's how Easy Ship sellers can tackle in-transit/customer-damaged returns") | Article byline: 15/02/2018. Page footer copyright: 2024. Accessed 2026-09-04 | No — public, Amazon India's own seller-facing marketing blog | SAFE-T mechanism definition, the filing steps (Orders > Manage SAFE-T Claims), Amazon's stated *response* time (7 business days), notification email address (`safe-t-review@amazon.com`), the one-claim-per-order-then-reply rule. **Notably does not state a filing-window day-count at all** — see Open Items |
| `https://sellercentral.amazon.in/seller-forums/discussions/t/3fc74ac2-d8d7-4eb6-af8a-2a78feb965f6` ("SAFE-T damage reimbursement policy" — original post authored by the official `News_Amazon` account) | Post: ~1 year before 2026-09-04 (thread timestamp "a year ago"). Accessed 2026-09-04 | No — public, read without an account | Quasi-primary: an official Amazon India policy-change announcement, effective 1 Aug 2025, naming a policy document by title ("SAFE-T Policy for Easy Ship, Self-Ship and Seller Flex orders: Terms and Conditions") and stating which return reasons (primary packaging/box damage, broken/open seals) stopped being reimbursable. India-confirmed: names Easy Ship, Self-Ship, Seller Flex explicitly |
| `https://www.youtube.com/watch?v=PPVglL7Z3w0` ("SAFE-T Claims \| Seller University \| Amazon India") | Published 5 Jan 2021 per video metadata. Accessed 2026-09-04 | No — public | Official Amazon India Seller University training video (channel: "Sell on Amazon India", 164k subscribers). Description confirms SAFE-T is scoped to Easy Ship/Self-Ship orders. Chapter markers read (0:00 What is SAFE-T, 2:45 Claim Granted/Denied, appeal section); full transcript not extracted this session |
| `https://sellercentral.amazon.in/help/hub/reference/G200897060` (attempted as the likely canonical Seller Central Help Hub SAFE-T policy/eligibility page) | Attempted 2026-09-04 | **Yes — confirmed.** Redirects to `sellercentral.amazon.in/ap/signin`; no content visible | **Node ID unverified.** This was my own best-guess URL pattern going in, not a URL surfaced by search — I could not find any independent citation of this specific ID, so I cannot confirm it is actually the SAFE-T reference page rather than some other or nonexistent page. What is confirmed: Seller Central's `/help/hub/reference/*` space requires an authenticated session; this lane did not attempt to sign in, per the rules |

### 1b. Secondary — India-focused integrator/service blogs

| URL | As of | Login-walled | Covers |
|---|---|---|---|
| `https://trackvid.in/blogs/amazon-safe-t-claim-india.html` ("Amazon SAFE-T Claim India: The 2026 Seller Guide to Winning Rejected Disputes") | Byline: TrackVid Team, 17 June 2026, "Updated June 2026". Accessed 2026-09-04 | No — public | India-focused (explicitly: "For sellers on Amazon, Flipkart, AJIO, Myntra and Meesho"). States a filing-window change (60→30 days effective 16 Feb 2026) and a 4-day inspection clock (effective 26 Jan 2026), both attributed to "seller reporting on MyAmazonGuy" and "Amazon Seller Forums" respectively, not to a primary Amazon citation. Contains the Delhi Seller Vikram case study — see §2, Example 2. Vendor content (TrackVid sells a video-evidence product); treat rule claims accordingly |
| `https://wareiq.com/resources/blogs/amazon-safe-t-claim/` ("SAFE-T Amazon Claim Guide for Sellers in 2026") | Byline: Mariyam Jameela, published 16 Feb 2024, "Last updated 15 Jan 2026". Accessed 2026-09-04 | No — public | WareIQ is an India fulfillment/logistics company. General SAFE-T Communication Center description; a distinct "SAFE-T Claim FBA Reimbursements" sub-flow for FBA sellers (see Open Items — this may be out of the B′ scope, which is seller-fulfilled/Easy Ship only); FAQ states Amazon's typical response window as "three to seven days" (response time, not filing deadline) |
| `https://myamazonguy.com/news/amazon-safe-t-claim-filing-window/` ("Amazon SAFE-T Claim Filing Window Cut to 30 Days For Sellers") | Not verified — see login/access note | **Blocked**, not login-walled: returned HTTP 403 to the headless browser on the one attempt made | Could not read. This is the page every other secondary source in this list traces the "30 days, cut from 60" figure back to. Since this lane could not open it, that figure has exactly zero primary or directly-read secondary confirmation in this research pass — it is hearsay-of-hearsay. Flagged as `verified: false` |
| `https://m.media-amazon.com/images/G/09/rainier/help/AtoZ_Guarantee_Program_Policy_PDF.pdf` ("A-to-z Guarantee Program Policy") | Not verified | Not verified — the URL triggers a direct file download rather than a renderable page; not downloaded/opened this session for time reasons | Surfaced by search as a candidate primary/authoritative A-to-Z policy PDF. Generic Amazon media CDN host carries no country marker, so whether this is the Amazon.in version or a global/US one is unconfirmed. Worth a follow-up download-and-read pass |

### 1c. Secondary — Amazon India Seller Central forum threads (India-confirmed: ₹ amounts, no "Country changed" banner)

All rows in this table are public and were read without any account — the
Seller Central forums allow anonymous read access to individual threads found
via search or direct link, even though the Help Hub reference pages (§1a) do
not.

| URL | As of (thread activity) | Covers |
|---|---|---|
| `.../seller-forums/discussions/t/a564524f-4777-4fc7-b55f-020b3ea50095` ("Safe-t issues and reimbursement") | Original post ~4 months before 2026-09-04; accessed 2026-09-04 | **A confirmed-granted SAFE-T claim with a named order, amounts, and an Amazon-staff reply confirming the grant.** Used as Example 1 in §2 |
| `.../seller-forums/discussions/t/9c284b79-4a98-44d1-aba4-072e220f3cd5` ("Safe-t-claim issue") | Original post ~10 months before 2026-09-04; accessed 2026-09-04 | A batch of 12 rejected claims (~₹1.5 lakh), rejection reason "exceeded the acceptable limit of filing SAFE-T claims"; an Amazon-staff reply (`Sakura_Amazon_`) citing an internal claims-to-return/reject abuse ratio of 8% and naming the policy document "SAFE-T Policy for Easy Ship, Self-Ship, and Seller Flex orders"; embedded sub-threads showing rejection-reason vocabulary (repeated images, images pre-dating the return, cross-account image reuse) |
| `.../seller-forums/discussions/t/fcb1ab29-b320-4c5a-ad39-184438140db2` ("Major Issues with Commission Charge on Refunds and Safe-T Claim Policy") | Original post ~3 years before 2026-09-04; accessed 2026-09-04 | A seller-support-style written complaint (not a SAFE-T claim) about **commission charged on refunds not being reversed** — directly relevant to class 5's mechanism and to the class-2/class-6 "files through support ticket, not SAFE-T" note in the brief. Also states a filing-window figure (15 days from refund) that **contradicts** the 30/60-day figures elsewhere — see Open Items. Lists real escalation email addresses sellers used (`in-safe-t@amazon.com`, `merch.service05@amazon.in`) |

Two threads seen only as embedded "Similar Discussions" teasers inside the
threads above (I did not independently open their own permalinks, so I cannot
fully vouch for their standalone content, only what rendered in the teaser):

- "Safe t claim-Amazon safe t team executive does not know their own policy" —
  Order 403-9515120-7790705, ₹36,000 at stake, claims the policy states a
  15-day filing window from refund, claim rejected as filed outside the window.
  Another contradiction data point on the day-count.
- "Appeal Request – SAFE-T Claim Denial and Reimbursement Amount" (Miracle
  Digital India) — a claim denied for an ASIN mismatch, then a follow-up
  dispute after additional evidence; outcome not stated in the teaser text.

### 1d. Found but not opened (lower priority; listed for completeness, not verified in any way)

- `.../seller-forums/discussions/t/fe6ce2ee-b0bc-4112-b2a6-15f6c7d28f3a` — "$2575 order lost in the mail, Safe-T claim DENIED even though the order page states CLAIMS PROTECTED" — dollar sign suggests US, not opened to confirm.
- `.../seller-forums/discussions/t/25ef73cf-f6c3-4943-9094-b734e2fd575e` — "Eligibility for A-to-z Guarantee on amazon" — not opened.
- `.../seller-forums/discussions/t/632fbc05-ce0a-4d7b-8769-e49357185214` — "SAFE T CLAIM DENIED" — not opened.
- `.../seller-forums/discussions/t/d601bb06-0d5c-47a5-83b4-b7127b087bb3` — "Denied SAFE-T Claims" — not opened.

### 1e. Checked and found to be region-mismatched (US content on an `.in`-hosted forum URL) — recorded so nobody re-cites these as India sources

| URL | Title | Tell |
|---|---|---|
| `.../seller-forums/discussions/t/caf6f9f1-5f82-4379-8c80-95b83aa3eb23` | "Let's Talk SAFE-T Claims!" (`Quincy_Amazon`) | "Country changed" banner to United States on load; replies discuss dollar amounts; contains eligible/ineligible-reason lists and two order IDs a seller cites as prior wins ("similar situation and Safe-T claims team paid us") but with no rupee amounts |
| `.../seller-forums/discussions/t/cfa1fdcd-a63c-4e75-b130-75a3a39a4f92` | "Filing SAFE-T claims: a step-by-step guide" (`KJ_Amazon`) | Same banner; $-denominated replies. Otherwise a detailed, Amazon-staff-authored eligible/ineligible list and a stated 7-day appeal-filing window — structurally the most complete single write-up found, just not confirmed to be Amazon.in's version of the policy |
| `.../seller-forums/discussions/t/3e25f42f-9bef-4971-ae5c-193798ca9f5c` | "How to file an appeal for an safe-t claim that was granted" | Same banner; $20/$3.99 amounts |
| `.../seller-forums/discussions/t/21a3017b-fb40-4d29-a835-35e6ecfbe859` | "Billed Seller fees - Twice" | Same banner; about a subscription-fee double-charge, not a marketplace fee dispute — low relevance even if it were India |

### 1f. Seller-facing fee-dispute / seller-support-case pages (class 2, class 6 — support-ticket mechanism)

No standalone, non-login-walled Amazon-authored page describing the
"fees charged in error" / general seller-support case-log workflow for
Amazon.in was found. What exists:

- The general shape of the workflow (Seller Central > Help > Contact Us, or
  Case Log > Create New Case; attach fee breakdowns/invoices; the case gets a
  trackable case ID) is described only by secondary summaries, most of them
  US-oriented (`sellercentral.amazon.com` forum threads, and blogs like
  Refunzo, Marketplace Valet). None of these are Amazon.in pages and none were
  opened directly given the time box — recorded as titles only, not as sources:
  a Seller Forums post "A Seller's Guide to Disputing Incorrect Charges on
  Amazon" and a Refunzo article "Ultimate Guide to Amazon Fee Discrepancy Logs".
- The one India-specific, India-confirmed data point on this mechanism is
  §1c's "Billed Seller fees - Twice" companion — actually that thread turned
  out to be US (see §1e); the genuinely India-confirmed support-ticket example
  is the commission-on-refunds complaint in §1c (`fcb1ab29...`), which is
  support-ticket-shaped (a written complaint to Seller Support) even though the
  underlying issue maps closer to class 5 (refund/fee reversal) than class 2.
- **Nothing India-specific and support-ticket-shaped was found for class 6**
  (unpaid order past cycle / absence from settlement). This is a real gap —
  see Open Items.

---

## 2. Winning claim examples

Two confirmed wins were found, both from Amazon.in Seller Central forum
threads read directly (public, no login). A third clean, confirmed-win,
India-specific example was not found in the time box; the closest additional
material is described below rather than mislabeled as a win.

### Example 1 — SAFE-T claim, granted (partial), damaged-item return

- **Source:** `https://sellercentral.amazon.in/seller-forums/discussions/t/a564524f-4777-4fc7-b55f-020b3ea50095`, posted by a seller (handle redacted-by-platform as `Seller_Khvtz4afkEEOq`) approximately 4 months before 2026-09-04; reply confirming the grant posted by Amazon staff account `Billy_Amazon` the same thread. Accessed 2026-09-04.
- **Claim type:** SAFE-T claim, reason code "item damaged" (Easy Ship / seller-fulfilled book order).
- **Structure of what the seller wrote**, paraphrased with structure preserved:
  - *Opening:* addressed to "fellow sellers and Amazon team," framed as flagging an unfair outcome and asking for escalation guidance, not a first-time filing.
  - *Order references:* full order ID, ASIN, purchase date, payment method (COD), and an itemized price breakdown (item price, shipping, total) given up front.
  - *What was lost:* the buyer's return reason was that the book arrived "completely damaged from the bottom"; the seller states they shipped a new, undamaged copy and that any damage happened in transit/handling, outside their control.
  - *Evidence attached:* the post lists order details, claim screenshots, and Amazon's confirmation email as available on request; the original SAFE-T filing (not shown in the forum post) would have required documentation per the standard filing flow.
  - *The ask:* three numbered requests — a transparent breakdown of how the reimbursed amount was calculated, an escalation to revise it toward the full loss, and guidance on the appeal mechanism.
- **Evidence attached (per the post):** order/claim screenshots and the Amazon confirmation email (referenced, not shown).
- **Outcome:** **Granted.** Amazon staff reply confirms the claim was granted and a partial amount (roughly 20% of the claimed loss) was credited. The seller's stated grievance is about the *amount*, not about winning the claim itself — useful signal that "won" and "made whole" are different outcomes worth keeping distinct in any claimability label.

### Example 2 — Aggregate case study, order-linked video evidence (not a single-claim narrative)

- **Source:** `https://trackvid.in/blogs/amazon-safe-t-claim-india.html`, "Delhi Seller Vikram" case study within a TrackVid (vendor) blog post, byline 17 June 2026. Accessed 2026-09-04.
- **Claim type:** SAFE-T claims generally, seller described as multi-category (electronics accessories + home goods), ~400 orders/day.
- **What's different about this example:** unlike Example 1, this is not one claim with one order reference — it's a vendor case study describing a change in *process* (packing video tagged to Order ID/SKU/AWB at pack time, attached to claims instead of reconstructed after the fact) and its effect on an aggregate approval rate, paraphrased as roughly 18% before, roughly 71% after, over one quarter, with the recovered total described only as "several lakh rupees" — no single order ID, no single amount.
- **Evidence pattern described:** order-linked packing video (specifically: video tagged to Order ID + SKU + AWB, captured at the moment of packing) attached at filing time, contrasted against three "weak proofs" the same article names — untagged CCTV footage, loose photos, and a written account with no linked proof.
- **The ask, generalized:** the article's own template for what a strong SAFE-T submission attaches is "the packing video for that Order ID, the AWB tracking record, and a short factual explanation" — evidence tied to one order beats a folder of generic material.
- **Outcome:** approval-rate improvement, not a single adjudicated claim. Treat as **structure and evidence-pattern signal**, not as a claim-text template the way Example 1 is. This is vendor marketing content; the specific percentages are TrackVid's own reporting, not independently audited.

### Third example — not found; closest material instead

Direct search for a third clean, confirmed-win, India-specific SAFE-T claim
did not succeed in the time box. What India Seller Central forum search
consistently surfaced instead was rejection and complaint threads — itself a
pattern worth naming (see Open Items). The two closest additional data points,
neither usable as a "winning claim" example as-is:

- A wrong-item-return dispute (product shipped: examination gloves; product
  returned: moisturizing cream) with full order-reference structure (order ID,
  a clear description of the mismatch, a request for re-investigation) but
  **denied**, under appeal, outcome not visible in the thread as read.
  Structurally complete (opening, order reference, loss, evidence claim, ask)
  — usable as a drafter structure template, not as a win.
- The two order IDs a US-marketplace seller cites as prior approved claims in
  `.../t/caf6f9f1-...` ("similar situation and Safe-T claims team paid us") —
  confirmed wins in structure, but on Amazon.com, not Amazon.in; excluded from
  the count above on region grounds, listed here only so the integrator knows
  it exists as a fallback if a third example is needed and region-purity is
  relaxed.

Per the design's own fallback (Open Question 4 / D14): if a third real example
is needed, the next-best option is templating from the cited policy language
in §1a/§1b and marking the template `verified: false`, rather than stretching
either item above into something it isn't.

---

## 3. Open items

**Pages not reached or not fully verified**
1. The canonical Seller Central Help Hub SAFE-T policy/eligibility page: login-walled, and the one node ID I tried was an unverified guess (see §1a). The real primary policy text — the document Amazon staff themselves call "SAFE-T Policy for Easy Ship, Self-Ship and Seller Flex orders: Terms and Conditions" — was never directly read. Design doc Open Question 3 ("Verify SAFE-T India window arithmetic and exclusions on live policy pages") is **not resolved** by this research pass; D14's fallback (secondary sources, `verified: false`) applies for Lane K.
2. `myamazonguy.com/news/amazon-safe-t-claim-filing-window/` returned HTTP 403 to the headless browser. This is the apparent root citation for the "30 days, cut from 60" figure that TrackVid and other blogs repeat — unread, unverified, `verified: false`.
3. Five of the seven A-to-Z Guarantee sub-pages linked from the overview page (§1a) were confirmed to exist by URL but their body text was not read this session (time box).
4. The A-to-Z Guarantee Program Policy PDF (`m.media-amazon.com/.../AtoZ_Guarantee_Program_Policy_PDF.pdf`) was found but not opened — it triggers a direct download rather than a page render; region (India vs global) unconfirmed.
5. No standalone Amazon.in page for the "fees charged in error" / seller-support case-log workflow was found (§1f); everything on that mechanism is either generic secondary summary or inferred from India forum replies describing what to do, not an Amazon-authored reference page.

**Contradictions between sources**
6. **Filing-window day-count has at least four different figures across sources, none traced to a primary page I could read:** 30 days (TrackVid, citing MyAmazonGuy, itself unread); 60 days, described as the pre-cut figure (same chain); 15 days (stated as-policy by two different India forum posters in two different threads, in both cases as the reason their claim was rejected — see §1c); a "reimbursed within 50 days of refund" figure (a third India forum poster, describing a promised timeline rather than a filing deadline, which may not be the same thing as a filing window at all). These may be reconciled by a real distinction this research could not confirm — e.g., different fulfillment channels (Easy Ship vs Self-Ship vs Seller Flex) or different trigger events (refund date vs return-delivery-scan date vs "returned/delivered to seller" date) carrying different windows — or some may simply be sellers misremembering or misquoting the policy in frustration. Lane K should not treat any single one of these as ground truth without reaching the primary page.
7. **Where in Seller Central SAFE-T lives seems to have moved over time.** The 2018 Amazon.in blog post (§1a) says Orders tab > Manage SAFE-T Claims. The 2026 TrackVid blog says Performance tab > A-to-Z Guarantee Claims > File a SAFE-T Claim. Both could be right at their respective dates; flagged in case it matters for any UI-shaped assumption anywhere downstream (it shouldn't, but noting it since navigation-path drift is otherwise an easy thing to bake in as if timeless).
8. A "4-day inspection window" (Guided Refund Workflow) and an "8% claims-to-return/reject abuse ratio" both appear exactly once each in the sources gathered (TrackVid for the former, an Amazon-staff forum reply for the latter) with no second, independent confirmation. Neither should be treated as confirmed by this pass.

**Signal on the mechanism enum (`SAFE-T | support-ticket | CA-review | none`)**
9. WareIQ (§1b) describes a distinct "SAFE-T Claim FBA Reimbursements" sub-flow, scoped to FBA sellers rather than Easy Ship/Self-Ship. The B′ design is seller-fulfilled only (design doc, "Known costs of B′"), so this is likely out of scope by construction — flagging only because it suggests SAFE-T is not one uniform mechanism across fulfillment channels, in case that assumption is load-bearing anywhere.
10. One India forum reply, in the course of routing a fee complaint, told the seller to escalate to Seller Support **and** to their account manager **and** gave named team email aliases (`in-safe-t@amazon.com`, `merch.service05@amazon.in`) as separate contact points. This hints at a real third channel — dedicated account-manager escalation — sitting alongside "file a SAFE-T claim" and "open a generic support case," which the two-value support-ticket bucket doesn't distinguish. Probably not worth modeling given the one-week build, but noted in case class-2/class-6 evidence requirements ever need to name *which* support channel.
11. No source found describes a class-6-shaped workflow (order paid to the customer but never settled to the seller, past the cycle window) as its own named case type — everything found under "support ticket" was fee- or refund-shaped, not absence-shaped. This is a real coverage gap in what this pass could find, not a claim that no such workflow exists.

**Pattern worth naming**
12. Searching India Seller Central forums for SAFE-T turns up rejection and complaint threads far more readily than confirmed wins — Example 1 in §2 was found only by following a "Similar Discussions" teaser link off an unrelated thread, not by direct search. Whether this reflects the actual approval-rate distribution, or just what sellers are motivated to post about, is not something this research can distinguish. Worth keeping in mind if the drafter or holdout design ever leans on "most claims look like X."

---

## 4. Coverage against the brief's minimum list

- SAFE-T policy/eligibility page(s) for Amazon.in — partial: no primary page read in full (login wall); one quasi-primary policy *announcement* read (§1a, `News_Amazon` post); two region-mismatched but structurally detailed Amazon-staff write-ups found (§1e) with unconfirmed India applicability.
- Filing-window statement — not resolved to one number; four conflicting secondary figures recorded (§ Open Items #6).
- Exclusions (A-to-Z claims, seller-issued refunds, other) — named explicitly only in the two region-mismatched US threads (§1e); not confirmed against an India-specific primary page.
- Evidence requirements for a claim — covered at the pattern level (order-linked proof, photos, tracking, invoices) across §1a (video), §1b (TrackVid/WareIQ), and §1c forum threads; no primary Amazon.in checklist page read in full.
- A-to-Z Guarantee policy page — covered, primary, confirmed (§1a, first two rows).
- Seller-facing fee-dispute / seller-support pages — largely not found as standalone Amazon.in pages; workflow shape only (§1f).
