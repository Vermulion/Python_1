"""Client profile: identity, contacts, age check, and owned accounts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from uuid import uuid4

from abstract_account import Owner
from bank_account import BankAccount

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_PATTERN = re.compile(r"^\+?[0-9]{7,15}$")
_MIN_AGE = 18


class ClientStatus(Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    CLOSED = "closed"


class UnderageClientError(ValueError):
    """Raised when a client is younger than 18."""


@dataclass
class Contacts:
    """Phones, email, and address of a client."""

    email: str
    phones: list[str] = field(default_factory=list)
    address: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.phones, str):
            self.phones = [self.phones]
        if not self.email.strip():
            raise ValueError("email is required")
        if not _EMAIL_PATTERN.match(self.email):
            raise ValueError(f"invalid email: {self.email}")
        if not self.phones:
            raise ValueError("at least one phone is required")
        cleaned: list[str] = []
        for phone in self.phones:
            number = str(phone).strip()
            if not _PHONE_PATTERN.match(number):
                raise ValueError(f"invalid phone: {phone}")
            cleaned.append(number)
        self.phones = cleaned
        self.address = self.address.strip()


class Client:
    """Bank client with identity, contacts, status, and a list of accounts."""

    _used_ids: set[str] = set()

    def __init__(
        self,
        first_name: str,
        surname: str,
        birth_date: date | str,
        contacts: Contacts,
        middle_name: str = "",
        client_id: str | None = None,
        status: ClientStatus = ClientStatus.ACTIVE,
    ) -> None:
        self.first_name = self._require_name(first_name, "first_name")
        self.middle_name = middle_name.strip()
        self.surname = self._require_name(surname, "surname")
        self.birth_date = self._parse_birth_date(birth_date)
        self._verify_age()
        if not isinstance(contacts, Contacts):
            raise TypeError("contacts must be a Contacts instance")
        self.contacts = contacts
        self.client_id = self._create_unique_id(client_id)
        if not isinstance(status, ClientStatus):
            raise TypeError("status must be ClientStatus")
        self.status = status
        self.accounts: list[BankAccount] = []
        self.failed_auth_attempts = 0
        self.tags: list[str] = []

    @property
    def full_name(self) -> str:
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.surname)
        return " ".join(parts)

    @property
    def age(self) -> int:
        today = date.today()
        years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years

    def as_owner(self) -> Owner:
        """Account owner snapshot used when opening an account."""
        return Owner(
            full_name=self.full_name,
            email=self.contacts.email,
            phone=self.contacts.phones[0],
        )

    def add_account(self, account: BankAccount) -> None:
        if not isinstance(account, BankAccount):
            raise TypeError("account must be a BankAccount")
        self.accounts.append(account)

    def find_account(self, account_id: str) -> BankAccount | None:
        for account in self.accounts:
            if account.account_id == account_id:
                return account
        return None

    def add_tag(self, tag: str) -> None:
        """Mark the client with a unique suspicious-action tag."""
        label = str(tag).strip()
        if not label:
            raise ValueError("tag must not be empty")
        if label not in self.tags:
            self.tags.append(label)

    def __str__(self) -> str:
        return (
            f"client: {self.full_name} | "
            f"id: {self.client_id} | "
            f"status: {self.status.value} | "
            f"age: {self.age} | "
            f"accounts: {len(self.accounts)}"
        )

    def _verify_age(self) -> None:
        if self.age < _MIN_AGE:
            raise UnderageClientError(
                f"client must be at least {_MIN_AGE}, got {self.age}"
            )

    @classmethod
    def _create_unique_id(cls, client_id: str | None) -> str:
        provided = str(client_id).strip() if client_id is not None else ""
        if provided:
            if provided in cls._used_ids:
                raise ValueError(f"client id already exists: {provided}")
            cls._used_ids.add(provided)
            return provided
        for _ in range(32):
            short_id = uuid4().hex[:8]
            if short_id not in cls._used_ids:
                cls._used_ids.add(short_id)
                return short_id
        raise RuntimeError("could not generate a unique short client id")

    @staticmethod
    def _require_name(value: str, field_name: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError(f"{field_name} must not be empty")
        return name

    @staticmethod
    def _parse_birth_date(birth_date: date | str) -> date:
        if isinstance(birth_date, date):
            return birth_date
        if isinstance(birth_date, str):
            try:
                return date.fromisoformat(birth_date)
            except ValueError as error:
                raise ValueError("birth_date must be YYYY-MM-DD") from error
        raise TypeError("birth_date must be date or str")
