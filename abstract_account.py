"""Step 1: abstract base for any bank account."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4


class AccountStatus(Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


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


@dataclass
class Owner:
    """Personal data of the account holder."""

    full_name: str
    email: str = ""
    phone: str = ""

    def __post_init__(self) -> None:
        if not self.full_name.strip():
            raise ValueError("owner full_name must not be empty")


class AbstractAccount(ABC):
    """Shared account fields and operations that subclasses must implement."""

    _used_ids: set[str] = set()

    def __init__(
        self,
        owner: Owner,
        opening_balance: float = 0.0,
        account_id: str | None = None,
    ) -> None:
        opening_balance = self._protect_from_negative(opening_balance, allow_zero=True)
        self.account_id = self._create_unique_id(account_id)
        self.owner = owner
        self._balance = opening_balance
        self.status = AccountStatus.ACTIVE

    @classmethod
    def _create_unique_id(cls, account_id: str | None) -> str:
        provided = str(account_id).strip() if account_id is not None else ""
        if provided:
            if provided in cls._used_ids:
                raise ValueError(f"account id already exists: {provided}")
            cls._used_ids.add(provided)
            return provided

        for _ in range(32):
            short_id = uuid4().hex[:8]
            if short_id not in cls._used_ids:
                cls._used_ids.add(short_id)
                return short_id
        raise RuntimeError("could not generate a unique short account id")

    def _protect_from_negative(self, amount: object, allow_zero: bool = False) -> float:
        """Reject negative, non-numeric, and (optionally) zero amounts."""
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise InvalidOperationError("amount must be a number")
        if amount != amount or amount in (float("inf"), float("-inf")):
            raise InvalidOperationError("amount must be a finite number")
        if amount < 0:
            raise InvalidOperationError("negative values are not allowed")
        if not allow_zero and amount == 0:
            raise InvalidOperationError("amount must be greater than 0")
        return round(float(amount), 2)

    def _check_account_status(self, operation: str) -> None:
        """Money operations are allowed only on an active account."""
        if self.status is AccountStatus.FROZEN:
            raise AccountFrozenError(f"cannot {operation}: account is frozen")
        if self.status is AccountStatus.CLOSED:
            raise AccountClosedError(f"cannot {operation}: account is closed")
        if self.status is not AccountStatus.ACTIVE:
            raise InvalidOperationError(
                f"cannot {operation}: account is {self.status.value}"
            )

    def _apply_credit(self, amount: float) -> float:
        """Add money and verify the new balance equals old + amount."""
        self._check_account_status("deposit")
        money = self._protect_from_negative(amount, allow_zero=False)
        previous = self._balance
        result = round(previous + money, 2)
        self._assert_sum(previous, money, result, add=True)
        self._balance = result
        return self._balance

    def _apply_debit(self, amount: float) -> float:
        """Subtract money and verify the new balance equals old - amount."""
        self._check_account_status("withdraw")
        money = self._protect_from_negative(amount, allow_zero=False)
        if money > self._balance:
            raise InsufficientFundsError(
                f"need {money}, but balance is {self._balance}"
            )
        previous = self._balance
        result = round(previous - money, 2)
        self._assert_sum(previous, money, result, add=False)
        self._balance = result
        return self._balance

    @staticmethod
    def _assert_sum(previous: float, amount: float, result: float, add: bool) -> None:
        expected = round(previous + amount, 2) if add else round(previous - amount, 2)
        if result != expected:
            raise InvalidOperationError("balance sum is incorrect")
        if result < 0:
            raise InvalidOperationError("balance cannot be negative")
        if add and result < previous:
            raise InvalidOperationError("deposit must increase the balance")
        if not add and result > previous:
            raise InvalidOperationError("withdrawal must decrease the balance")

    @abstractmethod
    def deposit(self, amount: float) -> float:
        """Add money to the account. Subclasses define the rules."""

    @abstractmethod
    def withdraw(self, amount: float) -> float:
        """Take money from the account. Subclasses define the rules."""

    @abstractmethod
    def get_account_info(self) -> dict[str, object]:
        """Return a snapshot of account data."""
