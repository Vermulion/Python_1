"""Bank: register clients and open, search, freeze, and close their accounts."""

from __future__ import annotations

from datetime import datetime, time
from typing import Callable

from abstract_account import AccountStatus, InvalidOperationError
from bank_account import BankAccount, Currency
from client import Client, ClientStatus
from investment_account import InvestmentAccount
from premium_account import PremiumAccount
from savings_account import SavingsAccount

ACCOUNT_TYPES: dict[str, type[BankAccount]] = {
    "checking": BankAccount,
    "bank": BankAccount,
    "savings": SavingsAccount,
    "premium": PremiumAccount,
    "investment": InvestmentAccount,
}

MAX_FAILED_AUTH_ATTEMPTS = 3
NIGHT_START = time(0, 0)
NIGHT_END = time(5, 0)

# Approximate rates to RUB used for totals and ranking.
RATES_TO_RUB: dict[Currency, float] = {
    Currency.RUB: 1.0,
    Currency.USD: 90.0,
    Currency.EUR: 100.0,
    Currency.KZT: 0.18,
    Currency.CNY: 12.5,
}

SUSPICIOUS_FAILED_AUTH = "failed_auth"
SUSPICIOUS_AUTH_LOCKED = "auth_locked"
SUSPICIOUS_NIGHT_OPERATION = "night_operation"
SUSPICIOUS_UNKNOWN_CLIENT = "unknown_client"


class Bank:
    """Collection of clients and the accounts opened for them."""

    def __init__(
        self,
        name: str = "Demo Bank",
        *,
        clock: Callable[[], datetime] | None = None,
        rates_to_rub: dict[Currency, float] | None = None,
    ) -> None:
        self.name = name.strip() or "Demo Bank"
        self._clients: dict[str, Client] = {}
        self._accounts: dict[str, BankAccount] = {}
        self._clock = clock or datetime.now
        self.rates_to_rub = dict(rates_to_rub or RATES_TO_RUB)
        self.suspicious_events: list[dict[str, object]] = []

    def add_client(self, client: Client) -> Client:
        if not isinstance(client, Client):
            raise TypeError("client must be a Client instance")
        if client.client_id in self._clients:
            raise InvalidOperationError(
                f"client already registered: {client.client_id}"
            )
        if client.status is ClientStatus.CLOSED:
            raise InvalidOperationError("cannot add a closed client")
        self._clients[client.client_id] = client
        for account in client.accounts:
            self._register_account(account)
        return client

    def authenticate_client(self, client_id: str, email: str) -> Client:
        """Confirm a registered active client by id and email.

        Three failed attempts block the client.
        """
        try:
            client = self._require_client(client_id)
        except InvalidOperationError:
            self._record_suspicious(
                SUSPICIOUS_UNKNOWN_CLIENT,
                client_id=str(client_id),
                detail="authentication against unknown client",
            )
            raise

        if client.status is ClientStatus.BLOCKED:
            raise InvalidOperationError(f"client is blocked: {client_id}")
        if client.status is ClientStatus.CLOSED:
            raise InvalidOperationError(f"client is closed: {client_id}")
        if client.contacts.email.casefold() != str(email).strip().casefold():
            client.failed_auth_attempts += 1
            self._record_suspicious(
                SUSPICIOUS_FAILED_AUTH,
                client_id=client.client_id,
                detail=f"failed attempt {client.failed_auth_attempts}",
            )
            if client.failed_auth_attempts >= MAX_FAILED_AUTH_ATTEMPTS:
                client.status = ClientStatus.BLOCKED
                client.add_tag(SUSPICIOUS_AUTH_LOCKED)
                self._record_suspicious(
                    SUSPICIOUS_AUTH_LOCKED,
                    client_id=client.client_id,
                    detail="blocked after 3 failed authentications",
                )
                raise InvalidOperationError(
                    f"authentication failed: client blocked after "
                    f"{MAX_FAILED_AUTH_ATTEMPTS} attempts"
                )
            raise InvalidOperationError("authentication failed")
        client.failed_auth_attempts = 0
        return client

    def open_account(
        self,
        client_id: str,
        account_type: str = "checking",
        opening_balance: float = 0.0,
        account_id: str | None = None,
        currency: Currency | str = Currency.RUB,
        **kwargs: object,
    ) -> BankAccount:
        self._forbid_night_operations("open_account", client_id)
        client = self._require_active_client(client_id)
        account_class = self._resolve_account_type(account_type)
        owner = client.as_owner()
        account = account_class(
            owner,
            opening_balance=opening_balance,
            account_id=account_id,
            currency=currency,
            **kwargs,
        )
        client.add_account(account)
        self._register_account(account)
        return account

    def close_account(self, account_id: str) -> BankAccount:
        self._forbid_night_operations("close_account", account_id=account_id)
        account = self._require_account(account_id)
        account.close()
        return account

    def freeze_account(self, account_id: str) -> BankAccount:
        self._forbid_night_operations("freeze_account", account_id=account_id)
        account = self._require_account(account_id)
        account.freeze()
        return account

    def unfreeze_account(self, account_id: str) -> BankAccount:
        self._forbid_night_operations("unfreeze_account", account_id=account_id)
        account = self._require_account(account_id)
        account.unfreeze()
        return account

    def search_accounts(
        self,
        *,
        account_id: str | None = None,
        client_id: str | None = None,
        status: AccountStatus | str | None = None,
        account_type: str | None = None,
    ) -> list[BankAccount]:
        """Find accounts by id, client, status, and/or class name."""
        matches = list(self._accounts.values())
        if account_id is not None:
            wanted = str(account_id).strip()
            matches = [item for item in matches if item.account_id == wanted]
        if client_id is not None:
            client = self._require_client(client_id)
            owned = {item.account_id for item in client.accounts}
            matches = [item for item in matches if item.account_id in owned]
        if status is not None:
            wanted_status = self._resolve_status(status)
            matches = [item for item in matches if item.status is wanted_status]
        if account_type is not None:
            class_name = self._resolve_account_type(account_type).__name__
            matches = [
                item for item in matches if type(item).__name__ == class_name
            ]
        return matches

    def get_total_balance(
        self,
        client_id: str | None = None,
        *,
        in_currency: Currency | str = Currency.RUB,
    ) -> float:
        """Sum account balances, converted to `in_currency` (default RUB)."""
        if client_id is None:
            accounts = list(self._accounts.values())
        else:
            accounts = self._require_client(client_id).accounts
        target = self._resolve_currency(in_currency)
        total = 0.0
        for account in accounts:
            if account.status is AccountStatus.CLOSED:
                continue
            amount = account.balance
            portfolio = getattr(account, "portfolio", None)
            if isinstance(portfolio, dict):
                amount += sum(portfolio.values())
            total += self._convert(amount, account.currency, target)
        return round(total, 2)

    def get_clients_ranking(
        self,
        *,
        in_currency: Currency | str = Currency.RUB,
    ) -> list[dict[str, object]]:
        """Clients ordered by total balance, richest first."""
        target = self._resolve_currency(in_currency)
        ranking: list[dict[str, object]] = []
        for client in self._clients.values():
            total = self.get_total_balance(client.client_id, in_currency=target)
            ranking.append(
                {
                    "client_id": client.client_id,
                    "full_name": client.full_name,
                    "status": client.status.value,
                    "total_balance": total,
                    "currency": target.value,
                    "accounts": len(client.accounts),
                    "tags": list(client.tags),
                }
            )
        ranking.sort(
            key=lambda row: (-float(row["total_balance"]), str(row["client_id"]))
        )
        return ranking

    def _convert(self, amount: float, source: Currency, target: Currency) -> float:
        if source is target:
            return float(amount)
        rub = float(amount) * self.rates_to_rub[source]
        return rub / self.rates_to_rub[target]

    def _is_night(self) -> bool:
        now = self._clock()
        current = now.time() if isinstance(now, datetime) else now
        return NIGHT_START <= current < NIGHT_END

    def _forbid_night_operations(
        self,
        operation: str,
        client_id: str | None = None,
        account_id: str | None = None,
    ) -> None:
        if not self._is_night():
            return
        if client_id is None and account_id is not None:
            account = self._accounts.get(str(account_id).strip())
            if account is not None:
                client_id = self._client_id_for_account(account)
        if client_id:
            client = self._clients.get(client_id)
            if client is not None:
                client.add_tag(SUSPICIOUS_NIGHT_OPERATION)
        self._record_suspicious(
            SUSPICIOUS_NIGHT_OPERATION,
            client_id=client_id,
            account_id=account_id,
            detail=f"{operation} blocked between 00:00 and 05:00",
        )
        raise InvalidOperationError(
            f"cannot {operation}: operations are prohibited from 00:00 until 05:00"
        )

    def _client_id_for_account(self, account: BankAccount) -> str | None:
        for client in self._clients.values():
            if any(item.account_id == account.account_id for item in client.accounts):
                return client.client_id
        return None

    def _record_suspicious(
        self,
        tag: str,
        *,
        client_id: str | None = None,
        account_id: str | None = None,
        detail: str = "",
    ) -> None:
        event: dict[str, object] = {
            "tag": tag,
            "at": self._clock(),
            "detail": detail,
        }
        if client_id is not None:
            event["client_id"] = client_id
        if account_id is not None:
            event["account_id"] = account_id
        self.suspicious_events.append(event)

    def _register_account(self, account: BankAccount) -> None:
        if account.account_id in self._accounts:
            raise InvalidOperationError(
                f"account already registered: {account.account_id}"
            )
        self._accounts[account.account_id] = account

    def _require_client(self, client_id: str) -> Client:
        key = str(client_id).strip()
        client = self._clients.get(key)
        if client is None:
            raise InvalidOperationError(f"unknown client: {client_id}")
        return client

    def _require_active_client(self, client_id: str) -> Client:
        client = self._require_client(client_id)
        if client.status is not ClientStatus.ACTIVE:
            raise InvalidOperationError(
                f"cannot open account: client is {client.status.value}"
            )
        return client

    def _require_account(self, account_id: str) -> BankAccount:
        key = str(account_id).strip()
        account = self._accounts.get(key)
        if account is None:
            raise InvalidOperationError(f"unknown account: {account_id}")
        return account

    @staticmethod
    def _resolve_account_type(account_type: str | type[BankAccount]) -> type[BankAccount]:
        if isinstance(account_type, type) and issubclass(account_type, BankAccount):
            return account_type
        key = str(account_type).strip().lower()
        if key in ACCOUNT_TYPES:
            return ACCOUNT_TYPES[key]
        allowed = ", ".join(sorted(ACCOUNT_TYPES))
        raise InvalidOperationError(
            f"unknown account type: {account_type}; use {allowed}"
        )

    @staticmethod
    def _resolve_status(status: AccountStatus | str) -> AccountStatus:
        if isinstance(status, AccountStatus):
            return status
        try:
            return AccountStatus(str(status).strip().lower())
        except ValueError as error:
            raise InvalidOperationError(f"unknown account status: {status}") from error

    @staticmethod
    def _resolve_currency(currency: Currency | str) -> Currency:
        if isinstance(currency, Currency):
            return currency
        try:
            return Currency(str(currency).strip().upper())
        except ValueError as error:
            raise InvalidOperationError(f"unknown currency: {currency}") from error


