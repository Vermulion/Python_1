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
        if opening_balance < 0:
            raise ValueError("opening balance cannot be negative")

        self.account_id = self._create_unique_id(account_id)
        self.owner = owner
        self._balance = opening_balance
        self.status = AccountStatus.ACTIVE

    @classmethod
    def _create_unique_id(cls, account_id: str | None) -> str:
        new_id = account_id or str(uuid4())
        if new_id in cls._used_ids:
            raise ValueError(f"account id already exists: {new_id}")
        cls._used_ids.add(new_id)
        return new_id

    @abstractmethod
    def deposit(self, amount: float) -> float:
        """Add money to the account. Subclasses define the rules."""

    @abstractmethod
    def withdraw(self, amount: float) -> float:
        """Take money from the account. Subclasses define the rules."""

    @abstractmethod
    def get_account_info(self) -> dict[str, object]:
        """Return a snapshot of account data."""
