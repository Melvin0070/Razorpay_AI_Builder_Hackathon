# Amazon India rate-card and tax sources (RS3)

Lane RS3 · Wave 0 · GitHub issue #3 · role `lp-research`. Research memo only —
**no fee percentage, slab amount, or tax rate appears anywhere below**, per the
brief's D12 independence requirement: Lane B (generator) and Lane C (rate-card
corpus) must each read the primary sources below and encode the numbers
independently. Where a cited source's own title contains a number, the title is
copied verbatim (per the brief's exception) — that is reporting what the source
is called, not asserting a rate.

All "as-of" dates below are the date I fetched/verified the page (**2026-09-04**,
via the `browse` skill headless Chromium) unless marked otherwise. `verified:
false` rows name why. WebSearch was used only to discover candidate URLs, never
as a source of fact for this memo; every URL below was independently loaded with
`browse` except where explicitly marked "not independently fetched."

---

## 1. Coverage decision

**Recommendation: keep the wireframe's three identifier strings, but pin two of
them to one specific Amazon fee-category node each. Do not treat any of the
three as covering a whole umbrella group.**

Amazon.in's referral-fee schedule (see §2) is organized as ~25-30 broad
"category" groups, each containing anywhere from one to dozens of named
**fee-category nodes**, each node carrying its own independent, price-tiered
referral-fee table. This matters directly for D17 ("every rule dated + URL-cited
... coverage declares category IDs"): a coverage declaration naming `apparel` or
`home-kitchen` as if either were a single rate table would be false.

| Identifier | Maps to a single real Amazon.in fee-category node? | Finding |
|---|---|---|
| `electronics-accessories` | **Yes, directly.** | "Electronics Accessories" is a real, exact fee-category node name, sitting inside the broader group Amazon itself labels "Electronics (Camera, Mobile, PC, Wireless) & Accessories." Use the identifier as-is; it names one rate table. |
| `home-kitchen` | **No.** | Amazon splits this across at least two broad groups with no single "Home & Kitchen" node: (a) "Home, Décor, Home Improvement, Furniture, Outdoor, Lawn & Garden" (nodes include Home Décor, Home Appliances, Home Improvement - Accessories, Home Furnishing, Home Storage, and others), and (b) "Kitchen, Large & Small Appliances" (nodes include Kitchen - Glassware & Ceramicware, Kitchen - Gas Stoves & Pressure Cookers, Kitchen Storage, Kitchen Tools & Supplies - Choppers/Knives/Bakeware & Accessories, Kitchen - Containers and Storage, Kitchen - Cookware, Tableware & Dinnerware, Kitchen - Other Products). **Recommend pinning `home-kitchen` to one specific node** — "Kitchen - Cookware, Tableware & Dinnerware" is a reasonable pick: unambiguous, demo-recognizable, and its own single rate table. "Home Appliances" is a reasonable alternative if the generator wants larger-ticket items. Lane C should confirm the final pick and cite the exact node name in the corpus. |
| `apparel` | **No.** | "Apparel" is not one node; it is a family of at least 13 named nodes under the group "Clothing, Fashion, Fashion Accessories, Jewellery, Luggage, Shoes": Apparel - Baby, Apparel - Dress, Apparel - Ethnic wear, Apparel - Shirts, Apparel - Shorts, Apparel - Sleepwear, Apparel - Socks and Stockings, Apparel - Sweat Shirts and Jackets, Apparel - Thermals, Apparel - Women's Innerwear and Lingerie, Apparel - Men's T-shirts (except Polos, Tank tops and full sleeve tops), Apparel - Accessories, Apparel - Other Products — each an independent rate table. **Recommend pinning `apparel` to one node**, e.g. "Apparel - Shirts" (high demand, unambiguous, gender/type-neutral phrasing exists in the schedule too if that's preferred). Lane C should confirm the final pick. |

**Price bands matter for all three.** Every fee-category node found (Electronics
Accessories, every Kitchen/Home node, every Apparel- node) prices its referral
fee in multiple item-price tiers, not a flat percentage. The exact tier
boundaries and rates are exactly the numbers this memo withholds — Lane B and
Lane C each read them off the live page independently. Closing fees are a
second, separate tiering: item-price band **crossed with** fulfilment channel
(Fulfilment Center / Easy Ship / Self Ship / Seller Flex) and a lettered/numbered
"Group" per category (e.g. the schedule groups categories into bands labeled
Group A, B, C, D, and others) — see §3.

**Is three categories the wrong cap?** Not on its own — but see Open Item 1
(§8): "three categories" only stays honest if each identifier is pinned to
exactly one real node, as recommended above. If any downstream lane instead
treats `apparel` or `home-kitchen` as covering everything a seller would
colloquially call apparel/home goods, the D17 coverage declaration becomes
false and synthetic orders tagged with the umbrella label will spuriously
UNCOVERED against a single pinned node's `lookup()`.

---

## 2. Referral (commission) fee sources

### Primary (Amazon.in, official)

| Source | URL | As-of | Login-walled | Covers |
|---|---|---|---|---|
| Amazon.in "Fees and Pricing" (public marketing/calculator page) | https://sell.amazon.in/fees-and-pricing | 2026-09-04 | No | Full referral-fee table inline, by category node, price-tiered; also hosts the fee calculators and the GST note (§4). No login required — reachable by anyone. |
| Amazon.in "Fee and Policy Update" / fee-schedule page | https://sell.amazon.in/fees-and-pricing/fee-schedule | 2026-09-04 | No | Same referral-fee table under anchor `#reffee-nodes`, plus a running explainer of the 2026 changes (see below) and a closing-fee section under anchor `#closefee` (§3). Not login-walled. |
| Amazon India official forum announcement: "Amazon.in fee updates, effective March 16, 2026" (posted by the `News_Amazon` account) | https://sellercentral.amazon.in/seller-forums/discussions/t/5edc203d-8623-4838-8ed3-b3fc6289cb45 | 2026-09-04 (post itself is dated ~6 months earlier per the page's own "6 months ago" stamp, i.e. ~March 2026) | **No** — Seller Forums discussion threads render fully without sign-in, unlike the Help Hub (§5). | Prose announcement of the March 16, 2026 referral-fee and closing-fee changes, with a link to the canonical schedule. Has an active reply thread from real sellers, useful context but not a source of rate figures. |
| Companion official post, "Amazon.in fee updates are now effective" (same `News_Amazon` account, linked from the post above) | https://sellercentral.amazon.in/seller-forums/discussions/t/17199174-ca9d-4d00-91d2-f86cf178f9b5 | not independently fetched — URL captured from a link on the verified post above; title and posting pattern match | presumed No, same forum namespace | Same March 16, 2026 change, "effective today" framing. `verified: false` — not independently opened. |

**The canonical, most complete schedule is login-walled.** The Seller Central
Help Hub's own reference page, titled "Selling on Amazon fee schedule," is
linked from the public schedule page above:

- https://sellercentral.amazon.in/help/hub/reference/G200336920 — confirmed
  **login-walled**: `browse goto` returns HTTP 200 but the rendered page is
  Amazon's sign-in form (`https://sellercentral.amazon.in/ap/signin?...`), not
  the fee schedule. `verified: false`, reason: requires an authenticated Seller
  Central session. This is the D14 fallback trigger for referral/closing fees:
  the two public `sell.amazon.in` pages above are the fallback, and they do
  carry the full category tables, so the fallback is not degraded here.

### 2026 changes found

Three distinct 2026 effective dates surfaced, not one:

1. **March 16, 2026** — broad referral-fee restructuring (zero-fee threshold
   expanded, reductions for several category groups, new fee-category nodes
   added). Primary: the two `sell.amazon.in` pages above and the forum
   announcement.
2. **June 10, 2026** — a narrower, category-specific referral-fee change,
   observed directly in the live table on `sell.amazon.in/fees-and-pricing` for
   at least "Automotive - Tyres & Rims" and "Fans and Robotic Vacuums" (the
   table shows one set of tiers "Until June 9, 2026" and a different set "From
   June 10, 2026"). No separate announcement page found for this date in the
   time available — flagged as Open Item 2.
3. **September 7, 2026** (closing fees, not referral — see §3) — imminent as of
   this memo's as-of date.

### Secondary (dated, for cross-reference only — not for lanes to copy numbers from)

| Source | URL | As-of (source's own date if stated) | Covers |
|---|---|---|---|
| ListingPilot, "Amazon Seller Fees in India 2026 (March Update): 0% Referral Under ₹1,000" | https://listingpilot.in/blog/amazon-seller-fees-india-2026/ | dated to the March 2026 update per title | Commentary on the March 16, 2026 change. Title copied verbatim (contains numbers). |
| KwickMetrics, "Amazon Referral Fee 2026 India: 0% Fees Under ₹1,000 Explained" | https://www.kwickmetrics.com/blog/amazon-referral-fee-2026-india | 2026 | Same change, independent write-up. Title copied verbatim. |
| Rekonsile, "Amazon India Fee Revision September 2025: Complete Guide to Referral, Closing, Shipping & Profitability fee changes" | https://rekonsile.com/amazon-india-fee-revision-september-2025-complete-guide | September 2025 | Documents the *prior* (2025) revision — useful for filling Open Item 3 (the undated "introduced in 2025" self-ship closing-fee baseline, §3). |
| Shiprocket, "Amazon Commission Rates in India (2026): Guide for Sellers" | https://www.shiprocket.in/blog/amazon-commission-rates-in-india/ | 2026 | Named explicitly in the brief. General referral-fee commentary. |
| Unicommerce, "How to Sell on Amazon India in 2026: Seller Guide" | https://unicommerce.com/blog/how-to-sell-on-amazon-india/ | 2026 | Named explicitly in the brief. General seller-fee commentary, broader than referral fees alone. |
| SW Cybernetics, "Amazon Seller Fees India 2026: Every Charge, Category-Wise" | https://swcybernetics.in/knowledge-base/amazon-seller-fees-india-complete-breakdown | 2026 | Category-wise breakdown, independent aggregator. |
| SellerApp, "Amazon Seller Repay Explained: Fees, Charges & How to Avoid Them" | https://www.sellerapp.com/blog/amazon-seller-repay/ | not stated on page | Named explicitly in the brief. **Caution:** written in `$` / US-marketplace terms in the passages surfaced during search, not `₹` / India terms — verify India-specific applicability before use; see §5. |

---

## 3. Closing fee sources

Same two primary URLs as §2 (`sell.amazon.in/fees-and-pricing` and
`.../fees-and-pricing/fee-schedule#closefee`) carry the closing-fee schedule:
fixed fee, tiered by item-price band, crossed with fulfilment channel
(Fulfilment Center, Easy Ship, Self Ship, Seller Flex) and by a
lettered/numbered category grouping the schedule itself defines (e.g. "Group A,"
"Group B," and similarly-labeled bands — the letters are Amazon's own grouping
key, not a rate). Both pages are public, not login-walled, verified 2026-09-04.

**Upcoming change, effective September 7, 2026** — three days after this
memo's as-of date. Found on `sell.amazon.in/fees-and-pricing/fee-schedule`:
Amazon states it is raising closing fees "due to an increase in logistics
costs," across the Fulfilment Center, Easy Ship, and Seller Flex channels.
Whatever `as_of` Lane B/Lane C's batches use, this date needs to be checked
against it — a batch dated on or after 2026-09-07 is under a different closing
fee schedule than one dated before it.

**Unresolved baseline date**: the pages state the *current* self-ship closing
fee band was "introduced in 2025" and carried forward through the March 16,
2026 update, but no exact 2025 date was found on either primary page in the
time available. The Rekonsile secondary source (§2) is dated September 2025 and
is the closest lead — flagged as Open Item 3.

The canonical Help Hub closing-fee reference lives at the same login-walled
`sellercentral.amazon.in/help/hub/reference/G200336920` page as the referral
schedule (§2) — same D14 fallback applies, same conclusion that the public
`sell.amazon.in` pages are an adequate fallback since they carry the full
tables.

---

## 4. GST on Amazon fees

**Primary**: https://sell.amazon.in/fees-and-pricing — the same page as §2.
Verified 2026-09-04, not login-walled. The page states, in a footnote, that all
fee figures displayed are shown **excluding** GST, and that Amazon applies GST
to all listed fee types. That is the entire fact this memo will state; the rate
itself is on that page for Lane B/Lane C to read directly.

**Secondary**: BizGrowth Pro, "GST on Amazon Seller Fees – GST Rate, ITC,
Accounting & Tax Rules Explained," https://www.bizgrowthpro.online/2026/07/gst-on-amazon-seller-fees-india.html,
dated July 2026 per URL path. Not independently fetched with `browse` (time-boxed);
`verified: false`. Useful if Lane C wants a plain-language walkthrough of how
GST-on-fees flows into ITC, which the primary page does not explain.

No separate PDF fee schedule was found anywhere on `sell.amazon.in` or linked
from it — the schedule is HTML-embedded on the two pages in §2/§3, not a
downloadable PDF. Worth recording since the brief anticipated a possible PDF.

---

## 5. Refund administration / refund commission fee

This is the weakest-sourced deliverable in this memo — flagged as Open Item 4.

**What the public pages do NOT have**: neither `sell.amazon.in/fees-and-pricing`
nor `.../fees-and-pricing/fee-schedule` mentions refunds, returns, or a
refund/return fee at all (checked by direct text search on both fetched pages,
zero matches).

**Primary, but login-walled**: two Seller Central Help Hub pages, found linked
from a public forum post (below) and confirmed independently:
- https://sellercentral.amazon.in/help/hub/reference/GU7K5N5GUP67M4X9
  ("Manage refunds") — confirmed login-walled (redirects to `/ap/signin`, same
  pattern as §2).
- https://sellercentral.amazon.in/help/hub/reference/G200708210
  ("Manage returns") — confirmed login-walled, same pattern.

**Best available public source**: an official Amazon India forum post (author
account `Noor_Amazon`, an Amazon staff account), publicly readable without
login, verified 2026-09-04 (post itself carries the page's own "2 years ago"
stamp, i.e. roughly 2024):
https://sellercentral.amazon.in/seller-forums/discussions/t/d18ac900-0473-44dc-911c-5038547ad53c
— titled "Do you want to know more about the Return Order Fee Structure?" It
names the fee **"Refund Commission"** as the India-marketplace term (distinct
from the US Seller Central term "Refund Administration Fee" — do not assume
the two mechanisms are identical without checking), states it is charged to
sellers when a customer returns an item, is based on item price, and offers a
waiver tied to the seller's STEP (Seller Performance and Target Enabler) level.
It links onward to "Manage refunds" and "Manage returns" — both login-walled,
above.

**Secondary, and off-marketplace — do not use for India figures**: SellerApp's
"Amazon Seller Repay Explained" (§2 secondary list) and a US Seller Central
Help Hub page, `https://sellercentral.amazon.com/help/hub/reference/external/GDC3U6FWF4JJJJC7`
(`.com`, not `.in`), describe the US "Refund Administration Fee" mechanism.
Not fetched (out of marketplace scope) — listed only so downstream lanes don't
accidentally cite a `.com` mechanism as if it were `.in` policy.

**Unverified, not opened**: a seller complaint thread titled "Return order fee
structure need to be review in favors of seller by Amazon.in,"
https://sellercentral.amazon.in/seller-forums/discussions/t/b8ef987ce70b86172f3ea54bd1feff6d
— found via search, not independently fetched, likely anecdotal rather than
authoritative. `verified: false`.

**Conclusion for D14**: the authoritative refund/return fee source is
login-walled with no public equivalent found (unlike referral/closing fees,
where the public `sell.amazon.in` pages are a full fallback). If class 5
("Refund without fee reversal") needs a cited fee rule rather than only the
event-pairing logic already in the design, Lane K/Lane C should budget time for
either a login-walled fetch (outside this lane's tooling) or accept the
`Noor_Amazon` forum post plus `verified: false` per D14.

---

## 6. Statutory sources

### Section 52 CGST Act — TCS by e-commerce operators

| Source | URL | As-of | Login-walled / blocked | Covers |
|---|---|---|---|---|
| CBIC official tax repository, consolidated CGST Act 2017 (HTML) | https://taxinformation.cbic.gov.in/content/html/tax_repository/gst/acts/2017_CGST_act/documents/Central_Goods_and_Services_Tax_Act__2017_28-September-2022.html | 2026-09-04 | No — loads (200), lists Section 52 ("Collection of tax at source") in its table of contents. Full operative text further down the page was not independently line-matched in the time available. | CBIC's own consolidated, amended Act text — the primary statutory reference. |
| CGST Act 2017, consolidated PDF (CBIC) | https://cbic-gst.gov.in/pdf/CGST-Act-Updated-31082021.pdf | 2026-09-04 | No — file downloads successfully. Dated 31.08.2021 in the filename; may predate amendments after that date (the Section 52(1) *statutory ceiling* text itself has not changed — only the *notified rate* has, by notification below, which does not require Act amendment). | Backup primary copy of the Act text. |
| India Code (Ministry of Law and Justice), original gazetted Act text | https://www.indiacode.nic.in/bitstream/123456789/15689/5/a2017-12.pdf (landing page: https://www.indiacode.nic.in/handle/123456789/15689) | not independently fetched | **Blocked** — `browse goto` returned HTTP 403 on the bitstream PDF. `verified: false`, reason: site returned 403 to the headless browser; unclear if a logged-out human browser fares better. | Authoritative original gazette text, Act No. 12 of 2017, if reachable by another tool. |
| CBIC / GST Council notification, original TCS rate | https://gstcouncil.gov.in/node/4059 ("52/2018-Central Tax," dated 20-09-2018) | 2026-09-04 | No — loads (200) | The notification issued under Section 52(1) setting the original TCS rate. Section 52(1) itself only sets a statutory *ceiling*; the applicable rate is fixed by notification, not by the Act text. |
| CBIC / GST Council notification, rate amendment | https://gstcouncil.gov.in/node/5015 ("15/2024-Central Tax," dated 10-07-2024) | 2026-09-04 | No — loads (200) | Amends the 2018 notification above — this is the rate-history event the brief asks for. |
| GST Council official FAQ on e-commerce (PDF) | https://gstcouncil.gov.in/sites/default/files/2024-02/faq-e-commerc.pdf | 2026-09-04 | No — file downloads successfully | Official (gstcouncil.gov.in-hosted) plain-language FAQ covering TCS mechanics, e-commerce operator obligations, GSTR-8 reporting. Quasi-primary — government-hosted but explanatory rather than statutory text. |

**Secondary, rate-history commentary** (titles copied verbatim per the
no-numbers rule, since each title itself carries the number):
- TaxScan, "CBIC notifies 0.25% TCS Rate for Intra-State Supplies of E-Commerce
  Operators," https://www.taxscan.in/cbic-notifies-0-25-tcs-rate-for-intra-state-supplies-of-e-commerce-operators/418067
- NYCA, "CBIC Reduces TCS Rate from 1% to 0.5% for E-Commerce Operators
  Effective July 10, 2024," https://www.nyca.in/cbic-reduces-tcs-rate-from-1-to-0-5-for-e-commerce-operators-effective-july-10-2024/

**Open item flagged by these two titles alone** (no numbers repeated here,
see §8 Open Item 5): the two secondary titles above describe what looks like
the same 10-07-2024 change with different headline figures. Both can be
correct simultaneously if one is quoting a combined (CGST+SGST) figure and the
other a single-leg figure — but that is exactly the kind of ambiguity Lane C
must resolve from the primary notification text (node/5015 above), not from
either blog title.

### Section 194-O Income-tax Act — TDS by e-commerce operators

| Source | URL | As-of | Login-walled / blocked | Covers |
|---|---|---|---|---|
| Income Tax Department, official section text | https://www.incometaxindia.gov.in/w/section-194-o | 2026-09-04 | **Blocked** — `browse goto` returns HTTP 403, page body is an Akamai "Access Denied" edge block (`errors.edgesuite.net`), not a login page. This is bot-blocking, not an account wall — a human browser may well succeed where headless automation did not. `verified: false`. | Would be the primary statutory text if reachable. |
| Income Tax Dept, CBDT press release PDF on Section 194-O guidelines (Circular 20/2023 context) | https://www.incometaxindia.gov.in/Lists/Press%20Releases/Attachments/1172/Press-Release-CBDT-issues-guidelines-194-O-of-the-Income-tax-Act-1961.pdf | 2026-09-04 | **Blocked**, same domain-wide 403 as above. `verified: false`. | Same domain block; the whole `incometaxindia.gov.in` host appears bot-walled, not just the one path. |
| PIB (Press Information Bureau), "CBDT issues guidelines under section 194-O of the Income-tax Act, 1961" | https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=1991334&reg=48&lang=2 | 2026-09-04 | **Blocked** — HTTP 403 to headless browse as well. `verified: false`. | Attempted as a workaround government source; also blocked. |
| Gazette of India, Finance (No. 2) Act, 2024 (full text, includes the Section 194-O rate amendment) | https://egazette.gov.in/WriteReadData/2024/256436.pdf | 2026-09-04 | No — file downloads successfully. | **This is the one confirmed-reachable primary statutory source for the 2024 change.** Section 194-O's rate is written directly into the section text (unlike Section 52's GST-notification mechanism above), so the Finance Act amendment itself is the primary source for the new rate — no separate CBDT notification needed for the rate figure itself. |

**Open item**: every `incometaxindia.gov.in` and `pib.gov.in` URL attempted
returned 403 to the headless browser in this session. This is a materially
different failure mode from Amazon's Help Hub login wall (§2, §5) — it is
edge/bot-blocking, not an authentication requirement — but the practical
consequence for an automated pipeline is the same: unreachable. D14's fallback
language ("secondary sources, each carrying `verified: false`") should be read
as covering this case too. The Gazette PDF above is the one primary source that
did work; recommend Lane K/Lane C anchor the 194-O rate-history citation there
rather than on the (correct, but unreachable-to-this-tooling) canonical
`incometaxindia.gov.in` section page.

**Secondary, rate-history commentary** (titles copied verbatim):
- Terra Insight, "Section 194O TDS at 0.1% (Was 1%): Current Rate History
  Under Income-tax Act 2025," https://www.terra-insight.com/insights/section-194o-tds-0-1-percent-current-rate-history-india/
- TaxGuru, "Change in TDS Rate Effective from 01st October 2024," https://taxguru.in/income-tax/change-tds-rate-effective-01st-october-2024.html

---

## 7. Compliance note

No fee percentage, price-band rupee amount, or tax rate figure was written
into this memo, including in places where the source material available to me
during research plainly stated one (e.g. the live `sell.amazon.in` referral and
closing-fee tables, and several secondary-source search snippets on the TCS/TDS
rate history). Where a source's own title contains a number, the title is
quoted verbatim, per the brief's stated exception, and nowhere else. Structural
facts that are not themselves rates — the existence and count of price tiers,
the existence of a zero-referral-fee tier as Amazon's own marketing claim, the
lettered/numbered closing-fee "Group" categories, statutory section numbers,
notification numbers, and effective dates — are reported, since the brief asks
for exactly this class of fact (coverage decision, "sub-category split that
matters, such as price bands," effective dates).

---

## 8. Open items

1. **Three-category cap is right-sized only if pinned, not if read as umbrella
   coverage.** See §1. `home-kitchen` and `apparel` are each families of a
   dozen-plus independent Amazon fee-category nodes, not single rate tables.
   Recommend the integrator confirm Lane C's corpus pins each identifier to one
   named node (candidates given in §1) before Lane B's generator starts
   emitting orders tagged with these identifiers, so the two encodings target
   the same real category.
2. **Three different 2026 effective dates found** (March 16, June 10,
   September 7 — §2, §3), plus an unresolved 2025 baseline date for the
   self-ship closing-fee reduction. No single "the 2026 schedule" exists;
   whichever `as_of` the generator's manifest uses needs to be checked against
   all of these, especially September 7, 2026, which lands three days after
   this memo's as-of date and inside any near-term build window.
3. **Self-ship closing-fee baseline date is not pinned.** Both primary pages
   say the current reduced self-ship closing fee was "introduced in 2025"
   without a specific date; the closest lead is the Rekonsile secondary
   source dated September 2025 (§2), not independently confirmed as the same
   event.
4. **Refund/return fee is the weakest-sourced deliverable.** The only
   authoritative pages (Help Hub "Manage refunds" / "Manage returns") are
   login-walled with no public equivalent found, unlike referral/closing fees
   where the public marketing pages are a full fallback. Best public source is
   a ~2024 official forum post naming the fee "Refund Commission" (India term,
   distinct from the US "Refund Administration Fee") but carrying no rate
   table. See §5.
5. **Two secondary sources on the same July 10, 2024 TCS change carry
   different headline figures** (§6) — plausibly a combined-rate vs.
   single-leg reporting inconsistency rather than a real disagreement, but
   unresolved without reading the primary notification text directly. Lane C
   must resolve this from `https://gstcouncil.gov.in/node/5015` itself, not
   from either secondary title.
6. **`incometaxindia.gov.in` and `pib.gov.in` are fully unreachable to this
   session's tooling** (HTTP 403, Akamai edge block, domain-wide — confirmed
   on three different paths). This blocks the single most canonical citation
   for Section 194-O's text. The Gazette of India PDF
   (`egazette.gov.in/WriteReadData/2024/256436.pdf`) is offered as the
   confirmed-reachable substitute primary source for the 2024 rate change; the
   bare Section 194-O text itself (as opposed to the amending Act) was not
   independently confirmed reachable by any tool available in this session.
7. **No PDF fee schedule exists on `sell.amazon.in`** — contrary to what the
   brief anticipated, the referral/closing fee schedule is HTML-embedded
   (two pages, §2/§3), not a downloadable PDF. Not a blocker, just a
   correction to the expected source shape.
8. **CGST Act primary text was confirmed reachable but not confirmed
   complete.** `taxinformation.cbic.gov.in`'s consolidated Act page (§6) loads
   and lists Section 52 in its table of contents; I did not independently
   confirm the full operative clause text renders below the fold in the time
   available. Worth a second check by whichever lane consumes it before
   treating it as fully verified.
