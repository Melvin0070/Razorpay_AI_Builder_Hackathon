"""Parsers and quarantine. Lane D · Tier C · issue #7.

Governed by D4, D7 and docs/specs/amazon-settlement-v2.md. Owns this package.
Consumes contract.classify_line / classify_transaction and the types below.
"""

from __future__ import annotations

from pathlib import Path

from leakproof.types import BankParse, OrdersParse, SellerProfile, SettlementFileParse


def parse_settlement_file(path: Path) -> SettlementFileParse:
    raise NotImplementedError("lane D, issue #7")


def parse_orders(path: Path) -> OrdersParse:
    raise NotImplementedError("lane D, issue #7")


def parse_bank(path: Path) -> BankParse:
    raise NotImplementedError("lane D, issue #7")


def load_profile(path: Path) -> SellerProfile:
    raise NotImplementedError("lane D, issue #7")
