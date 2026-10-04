"""Step 2: concrete bank account with validation, status rules, and currency."""

from __future__ import annotations

import re
from enum import Enum

from abstract_account import AbstractAccount, AccountStatus, Owner


class Currency(Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    KZT = "KZT"
    CNY = "CNY"


class BankError(Exception):
    """Base error for bank account operations."""


class AccountFrozenError(BankError):
    """Raised when the account is frozen and the operation is not allowed."""


class AccountClosedError(BankError):
    """Raised when the account is closed and the operation is not allowed."""


class InvalidOperationError(BankError):
    """Raised when the operation is invalid for the current data or status."""


class InsufficientFundsError(BankError):
    """Raised when a withdrawal exceeds the balance."""


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_PATTERN = re.compile(r"^\+?[0-9]{7,15}$")


class BankAccount(AbstractAccount):
    """Checking-style account with currency, validation, and status rules."""

    def __init__(
        self,
        owner: Owner,
        opening_balance: float = 0.0,
        account_id: str | None = None,
        currency: Currency | str = Currency.RUB,
    ) -> None:
        self._validate_owner(owner)
        opening_balance = self._validate_money(opening_balance, allow_zero=True)
        currency = self._validate_currency(currency)
        super().__init__(owner, opening_balance, account_id)
        self.currency = currency

    def deposit(self, amount: float) -> float:
        self._ensure_open_for("deposit")
        money = self._validate_money(amount, allow_zero=False)
        self._balance += money
        return self._balance

    def withdraw(self, amount: float) -> float:
        self._ensure_open_for("withdraw")
        money = self._validate_money(amount, allow_zero=False)
        if money > self._balance:
            raise InsufficientFundsError(
                f"need {money} {self.currency.value}, but balance is {self._balance}"
            )
        self._balance -= money
        return self._balance

    def freeze(self) -> None:
        if self.status is AccountStatus.FROZEN:
            raise InvalidOperationError("account is already frozen")
        if self.status is AccountStatus.CLOSED:
            raise AccountClosedError("cannot freeze: account is closed")
        self.status = AccountStatus.FROZEN

    def unfreeze(self) -> None:
        if self.status is AccountStatus.CLOSED:
            raise AccountClosedError("cannot unfreeze: account is closed")
        if self.status is not AccountStatus.FROZEN:
            raise InvalidOperationError("cannot unfreeze: account is not frozen")
        self.status = AccountStatus.ACTIVE

    def close(self) -> None:
        if self.status is AccountStatus.CLOSED:
            raise AccountClosedError("account is already closed")
        self.status = AccountStatus.CLOSED

    def get_account_info(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "owner": self.owner.full_name,
            "email": self.owner.email,
            "phone": self.owner.phone,
            "balance": self._balance,
            "currency": self.currency.value,
            "status": self.status.value,
        }

    def _ensure_open_for(self, operation: str) -> None:
        if self.status is AccountStatus.FROZEN:
            raise AccountFrozenError(f"cannot {operation}: account is frozen")
        if self.status is AccountStatus.CLOSED:
            raise AccountClosedError(f"cannot {operation}: account is closed")

    @staticmethod
    def _validate_owner(owner: Owner) -> None:
        if not isinstance(owner, Owner):
            raise TypeError("owner must be an Owner instance")
        if owner.email and not _EMAIL_PATTERN.match(owner.email):
            raise ValueError(f"invalid email: {owner.email}")
        if owner.phone and not _PHONE_PATTERN.match(owner.phone):
            raise ValueError(f"invalid phone: {owner.phone}")

    @staticmethod
    def _validate_money(value: object, allow_zero: bool) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidOperationError("amount must be a number")
        if value != value or value in (float("inf"), float("-inf")):
            raise InvalidOperationError("amount must be a finite number")
        if value < 0 or (not allow_zero and value == 0):
            raise InvalidOperationError("amount must be greater than 0")
        return float(value)

    @staticmethod
    def _validate_currency(currency: Currency | str) -> Currency:
        if isinstance(currency, Currency):
            return currency
        if isinstance(currency, str):
            try:
                return Currency(currency.upper())
            except ValueError as error:
                allowed = ", ".join(item.value for item in Currency)
                raise ValueError(f"currency must be one of: {allowed}") from error
        raise TypeError("currency must be Currency or str")
