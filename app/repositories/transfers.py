"""Money transfer between accounts.

The application validates the input and checks that the sender account belongs to the client.
Everything that concerns money is decided by the database: the ``on_transfer`` trigger
(see db/schema.sql) locks both accounts in a fixed order, verifies the balance and applies the
transfer atomically. Errors of the database are translated into messages for the user.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

import psycopg2

from app import db, sql

# Same format as the account_number domain of the database (8-12 digits). It is validated before
# the value reaches the database, because casting a malformed value to the domain is an error.
ACCOUNT_NUMBER_RE = re.compile(r"[0-9]{8,12}")
MAX_AMOUNT = Decimal("999999999.99")

_INSUFFICIENT_FUNDS = "RIS02"  # SQLSTATE raised by the on_transfer trigger
_RECEIVER_FKEY = "remittances_receiver_fkey"


class TransferError(Exception):
    """An error whose message is safe to show to the user."""


def parse_amount(raw: str) -> Decimal:
    try:
        value = Decimal(raw.strip().replace(",", "."))
    except InvalidOperation:
        raise TransferError("Некорректная сумма перевода") from None
    if (
        not value.is_finite()
        or value <= 0
        or value > MAX_AMOUNT
        or value.as_tuple().exponent < -2  # at most two decimal places
    ):
        raise TransferError("Некорректная сумма перевода")
    return value


def _translate(exc: psycopg2.Error) -> TransferError | None:
    if exc.pgcode == _INSUFFICIENT_FUNDS:
        return TransferError("Недостаточно средств на счёте")
    if exc.pgcode == "23503" and exc.diag.constraint_name == _RECEIVER_FKEY:
        return TransferError("Счёт получателя не найден")
    return None


def make_transfer(*, contract_num: str, sender: str, receiver: str, amount_raw: str) -> None:
    amount = parse_amount(amount_raw)
    if not ACCOUNT_NUMBER_RE.fullmatch(sender):
        raise TransferError("Счёт списания не найден")
    if not ACCOUNT_NUMBER_RE.fullmatch(receiver):
        raise TransferError("Некорректный номер получателя")
    if sender == receiver:
        raise TransferError("Нельзя перевести деньги на тот же счёт")

    try:
        updated = db.execute(
            sql.load("remittances/insert.sql"),
            {"amount": amount, "sender": sender, "receiver": receiver, "contract_num": contract_num},
        )
    except psycopg2.Error as exc:
        translated = _translate(exc)
        if translated is None:
            raise
        raise translated from None
    if updated != 1:  # the sender account does not exist or belongs to another client
        raise TransferError("Счёт списания не найден")
