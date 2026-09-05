"""Parsers and quarantine (D4, D7). Lane D · Tier C · issue #7.

Every file parser here (settlement, orders, bank) is pure file-in, record-out
and never raises on malformed *row* content: a bad row becomes a
``QuarantinedRow`` (line_id + reason) instead of an exception, and stays in
the match-rate denominator (D7). An unknown vocabulary code is a different
thing and is *not* quarantined -- ``contract.classify_line`` /
``classify_transaction`` map it to ``LineKind.UNCLASSIFIED`` /
``TransactionType.OTHER``, the raw string is kept on the line, and it is
returned as ordinary data (D4). ``FileNotFoundError`` is the one exception
every one of these three still lets through -- there is no per-row citation
for "the file does not exist" (the integrator's job per parser).

``load_profile`` is not one of those three: a seller profile is config, not
user-uploaded data with rows to quarantine, so malformed content deliberately
*raises* ``ProfileError`` (naming the file and the cause, S13) rather than
degrading -- see ``profile.py``'s own docstring. ``FileNotFoundError`` still
applies to a missing profile file, same as the other three.

Encoding, blank lines and physical numbering (the three file parsers):
  * A leading UTF-8 BOM on row/record 1 is stripped before anything else is
    parsed (all four loaders, ``load_profile`` included as of G10); it never
    causes a header mismatch or a bogus "invalid JSON".
  * A physical line containing one or more bytes that are not valid UTF-8 is
    decoded with ``errors="surrogateescape"`` (undecodable bytes become lone
    surrogates U+DC80-U+DCFF) and quarantined with ``not valid UTF-8`` --
    only that row; the rest of the file still parses. The settlement parser
    reads the file as bytes and splits with ``bytes.splitlines()`` (breaks
    only on ``\\n``, ``\\r``, ``\\r\\n``), not ``str.splitlines()`` (which
    also breaks on ``\\v``, ``\\f``, U+001C-U+001E and U+0085 and would shift
    every later ``line_id`` off what a text editor shows).
  * A physical line that is empty once whitespace is stripped is skipped --
    never quarantined -- in all three row parsers; the physical line_id
    counter still advances past it (a trailing or interior blank line never
    manufactures a phantom quarantined row in the D7 denominator). A row that
    tab- or comma-splits to *more than one* empty field (e.g. 24 empty
    tab-separated fields, or a bare ``,,,,``) is not this case (G5): it is
    malformed data, not a blank line, and is left to the ordinary per-field
    checks below -- the settlement parser and the orders/bank CSVs agree on
    this.
  * The orders and bank CSV parsers track physical line numbers via
    ``csv.reader.line_num`` rather than a plain row counter, so a quoted
    field with an embedded newline (e.g. a bank narration) does not shift
    every later row's citation off its physical line. The ``StringIO`` they
    read from is opened with ``newline=""`` (G1): without it, a bare ``\\r``
    line ending (an Excel-for-Mac export, or a stray ``\\r`` inside a
    narration) is not recognised as a line ending at all and ``csv.reader``
    raises ``_csv.Error`` out of the whole file with no line_id.

Header validation (all three file parsers): the header row must match its
canonical column names exactly, not just the column count. On any mismatch,
nothing downstream is parsed by guessed column position:
  * row 1 (or the first CSV record) is quarantined ``expected N ...columns,
    found M`` if the column count itself is wrong, else ``unknown header
    layout``;
  * every later non-blank row is quarantined with the same stable reason,
    ``not parsed: unknown header layout``, in all three file parsers (G2).
    The settlement parser's row 2 (summary) and transaction rows are *not*
    read at fixed offsets once row 1's names cannot be trusted, even though
    the column count was right -- a transposed pair of columns (e.g.
    ``total-amount``/``amount``) is exactly the case fixed offsets would get
    wrong silently. This cascade is gated on the column count being 24: a
    settlement header whose count itself is wrong (saved-as-CSV, a trailing
    tab) already quarantines every row on its own column-count mismatch, and
    that reason -- not the cascade -- is what the hint names (S5).
  * ``hint`` names the expected first column of that format.

Quarantine reasons, exact and stable (defined in ``leakproof.ingest.reasons``;
shown on screen verbatim, so wording changes are interface changes):

Settlement file (docs/specs/amazon-settlement-v2.md), the five named in the
lane brief, plus this round's additions:
  * ``expected 24 tab-separated columns, found N`` -- any row (header,
    summary, or transaction) whose tab-split field count is not 24.
  * ``amount not numeric: '...'`` -- ``total-amount`` (summary) or ``amount``
    (transaction) does not parse under the file's detected decimal separator
    (trap 1): no thousands separator, exactly two fractional digits. The
    separator is detected from the summary row's ``total-amount`` first;
    if that is missing, unreadable, or the summary row itself is missing
    (see the S7/G4 cases below), by corroborating a majority vote across up
    to five transaction rows whose ``amount`` contains ``.`` or ``,`` (G6:
    a single typo'd amount must not flip the whole file's separator and
    quarantine every well-formed row behind it); only then does it default
    to ``.``. When more than one row ends up quarantined on this reason,
    ``hint`` names the separator that was detected, since a genuine
    file-wide convention mismatch -- not a typo -- is the likelier cause.
  * ``bad date in <column>: '...'`` -- a date is not one of the three
    accepted forms (trap 3). ``<column>`` is ``settlement-start-date``,
    ``settlement-end-date`` or ``deposit-date`` (summary row) or
    ``posted-date`` (transaction row).
  * ``missing order-id on Order row`` -- ``transaction-type`` classifies as
    ``TransactionType.ORDER`` (trap 2) but ``order-id`` is empty.
  * ``unknown header layout`` -- row 1 has 24 tab-separated fields, but they
    are not the 24 canonical column names in order.
  * ``not parsed: unknown header layout`` -- every row 2+ once row 1's names
    fail the check above (G2).
  * ``quantity not numeric: '...'`` -- a non-empty ``quantity-purchased``
    that is not a plain integer.
  * ``quantity not positive: '...'`` -- ``quantity-purchased`` parses but is
    ``<= 0`` (G9, matching the orders CSV's own rule for the same concept).
  * ``not valid UTF-8`` -- see "Encoding, blank lines and physical
    numbering" above.

Orders CSV (companion format, same spec doc, "Companion inputs"):
  * ``expected 9 comma-separated columns, found N``
  * ``unknown header layout`` / ``not parsed: unknown header layout`` -- see
    "Header validation" above.
  * ``not valid UTF-8``
  * ``missing order_id``
  * ``quantity not numeric: '...'`` -- ``quantity`` is not a plain integer.
  * ``quantity not positive: '...'`` -- ``quantity`` parses but is ``<= 0``.
  * ``amount not numeric: '...'`` -- ``principal_paise`` / ``tax_paise`` are
    already integer paise per the column name (no decimal point expected);
    anything that is not a plain integer gets this reason.
  * ``principal negative: '...'`` / ``tax negative: '...'`` -- parses but is
    negative.
  * ``bad date in order_date: '...'`` / ``bad date in delivery_date: '...'``
  * ``delivery_date before order_date`` -- exact string named by the brief.
    An *empty* ``delivery_date`` is not an error (``Order.delivery_date`` is
    ``None``); only a delivery date earlier than the order date quarantines.
  * ``unknown refund_initiated_by: '...'`` -- not one of
    ``{none, seller, amazon}``, compared case-insensitively.

Bank CSV (companion format):
  * ``expected 4 comma-separated columns, found N``
  * ``unknown header layout`` / ``not parsed: unknown header layout`` -- see
    "Header validation" above.
  * ``not valid UTF-8``
  * ``bad date in date: '...'``
  * ``missing utr``
  * ``amount not numeric: '...'``

Seller profile (JSON, not a quarantine case -- see above): every fault raises
``ProfileError`` naming the path and the cause (S13):
  * not valid UTF-8; invalid JSON.
  * the top level is valid JSON but not a JSON object (``[]``, a bare
    string, ``null``, a bare number) -- the commonest hand-edit mistake
    (G3).
  * ``capabilities`` is present but is not a JSON array, or one of its
    entries is not a JSON object (G3).
  * a required key (``seller_id``, ``display_name``, a capability's
    ``name``/``holds``) is missing.
  * ``seller_id`` or ``display_name`` is present but is not a string (G3),
    e.g. ``{"seller_id": 123, ...}``.
  * a capability's ``valid_from``/``valid_to`` does not parse under the same
    date grammar every other parser uses (``parsing.parse_flexible_date``,
    G10) -- not the more permissive ``date.fromisoformat``, which also
    accepts forms the spec never lists (``20260101``, ``2026-W01-1``).

``hint`` (wireframe frame 4, "Nothing parsed"). Checked in this order for the
settlement file; the orders and bank CSVs only ever produce the header one:
  * every non-blank physical row (header included) tab-splits to exactly one
    field -> "the file was saved as CSV; Amazon Settlement Flat File V2 is
    tab-separated" (settlement file only).
  * every non-blank physical row has exactly 25 tab-separated fields with the
    last one empty -> "every row has one extra empty column: a trailing tab;
    Amazon Settlement Flat File V2 has 24 tab-separated columns" (settlement
    file only; a stray trailing tab on every line, not genuine malformation --
    the rows are still quarantined on the ordinary column-count reason above,
    only the hint names the more useful cause).
  * row 2 carries a non-empty ``transaction-type`` *and* a non-empty
    ``amount`` (two tells, G7 -- this row-2 layout is spec ``verified:
    false``, so one weak signal is not enough) -- it is a transaction row,
    not the summary, so the summary row itself is missing from the file ->
    "summary row missing: row 2 is a transaction row" (settlement file only;
    no rows are dropped: parsing proceeds treating every row from 2 onward
    as a transaction line, ``header`` is ``None``).
  * row 2 is blank, or the file has fewer than two rows (G4) -> "summary row
    missing: row 2 is blank" (settlement file only; same effect on
    ``header`` as the case above, but S6 never quarantines the blank row
    itself, so this hint is the only signal).
  * otherwise, on a header mismatch (row 1, or the first CSV record, quarantined
    per "Header validation" above) -> names the expected first column of that
    format: ``settlement-id`` (settlement file), ``order_id`` (orders CSV),
    ``date`` (bank CSV).
  * otherwise, when detection could not be corroborated and more than one row
    quarantines with ``amount not numeric`` (G6, settlement file only) ->
    names the separator that was detected.
"""

from __future__ import annotations

from leakproof.ingest.bank import parse_bank
from leakproof.ingest.orders import parse_orders
from leakproof.ingest.profile import ProfileError, load_profile
from leakproof.ingest.settlement import parse_settlement_file

__all__ = ["ProfileError", "load_profile", "parse_bank", "parse_orders", "parse_settlement_file"]
