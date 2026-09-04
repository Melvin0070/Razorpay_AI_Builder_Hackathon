"""Parsers and quarantine (D4, D7). Lane D · Tier C · issue #7.

Every parser here is pure file-in, record-out and never raises on malformed
input: a bad row becomes a ``QuarantinedRow`` (line_id + reason) instead of an
exception, and stays in the match-rate denominator (D7). An unknown
vocabulary code is a different thing and is *not* quarantined --
``contract.classify_line`` / ``classify_transaction`` map it to
``LineKind.UNCLASSIFIED`` / ``TransactionType.OTHER``, the raw string is kept
on the line, and it is returned as ordinary data (D4).

Quarantine reasons, exact and stable (defined in ``leakproof.ingest.reasons``;
shown on screen verbatim, so wording changes are interface changes):

Settlement file (docs/specs/amazon-settlement-v2.md), the five named in the
lane brief:
  * ``expected 24 tab-separated columns, found N`` -- any row (header,
    summary, or transaction) whose tab-split field count is not 24.
  * ``amount not numeric: '...'`` -- ``total-amount`` (summary) or ``amount``
    (transaction) does not parse under the file's detected decimal separator
    (trap 1): no thousands separator, exactly two fractional digits.
  * ``bad date in <column>: '...'`` -- a date is not one of the three
    accepted forms (trap 3). ``<column>`` is ``settlement-start-date``,
    ``settlement-end-date`` or ``deposit-date`` (summary row) or
    ``posted-date`` (transaction row).
  * ``missing order-id on Order row`` -- ``transaction-type`` classifies as
    ``TransactionType.ORDER`` (trap 2) but ``order-id`` is empty.
  * ``unknown header layout`` -- row 1 has 24 tab-separated fields, but they
    are not the 24 canonical column names in order.

This lane's own addition, same style, for the settlement file and reused
verbatim by the orders CSV:
  * ``quantity not numeric: '...'`` -- a non-empty ``quantity-purchased`` (or
    orders-CSV ``quantity``) that is not a plain integer.

Orders CSV (companion format, same spec doc, "Companion inputs"):
  * ``expected 9 comma-separated columns, found N``
  * ``missing order_id``
  * ``amount not numeric: '...'`` -- ``principal_paise`` / ``tax_paise`` are
    already integer paise per the column name (no decimal point expected);
    anything that is not a plain integer gets this reason.
  * ``bad date in order_date: '...'`` / ``bad date in delivery_date: '...'``
  * ``delivery_date before order_date`` -- exact string named by the brief.
    An *empty* ``delivery_date`` is not an error (``Order.delivery_date`` is
    ``None``); only a delivery date earlier than the order date quarantines.
  * ``unknown refund_initiated_by: '...'`` -- not one of
    ``{none, seller, amazon}``, compared case-insensitively.

Bank CSV (companion format):
  * ``expected 4 comma-separated columns, found N``
  * ``bad date in date: '...'``
  * ``missing utr``
  * ``amount not numeric: '...'``

``hint`` (settlement file only; wireframe frame 4, "Nothing parsed"):
  * every physical row (header included) tab-splits to exactly one field ->
    "the file was saved as CSV; Amazon Settlement Flat File V2 is
    tab-separated".
  * otherwise, no ``SettlementHeader`` could be built (row 1 or row 2 is
    unreadable) -> names the expected first column, ``settlement-id``.
  Orders and bank parsers do not set ``hint``: they have no equivalent
  wrong-file-format signal to name (a genuinely wrong file just produces a
  wall of ``expected N comma-separated columns`` quarantines instead).
"""

from __future__ import annotations

from leakproof.ingest.bank import parse_bank
from leakproof.ingest.orders import parse_orders
from leakproof.ingest.profile import load_profile
from leakproof.ingest.settlement import parse_settlement_file

__all__ = ["load_profile", "parse_bank", "parse_orders", "parse_settlement_file"]
