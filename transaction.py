"""Transfers: transaction records, a priority queue, and a processor."""

from __future__ import annotations

import heapq
from datetime import datetime
from enum import Enum
from typing import Callable
from uuid import uuid4

from abstract_account import (
    AccountClosedError,
    AccountFrozenError,
    AccountStatus,
    InsufficientFundsError,
    InvalidOperationError,
)
from audit_log import AuditLog, LogLevel
from bank import Bank
from bank_account import BankAccount, Currency
from premium_account import PremiumAccount
from risk_analyzer import (
    AuditReporter,
    DangerousTransactionError,
    RiskAnalyzer,
    RiskLevel,
)
from savings_account import SavingsAccount


class TransactionType(Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class TransactionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


def _money(value: object, field_name: str, allow_zero: bool = False) -> float:
    dummy = BankAccount.__new__(BankAccount)
    try:
        return BankAccount._protect_from_negative(dummy, value, allow_zero=allow_zero)
    except InvalidOperationError as error:
        raise InvalidOperationError(f"{field_name}: {error}") from error


def _resolve_type(tx_type: TransactionType | str) -> TransactionType:
    if isinstance(tx_type, TransactionType):
        return tx_type
    try:
        return TransactionType(str(tx_type).strip().lower())
    except ValueError as error:
        allowed = ", ".join(item.value for item in TransactionType)
        raise InvalidOperationError(f"type must be one of: {allowed}") from error


def _resolve_currency(currency: Currency | str) -> Currency:
    if isinstance(currency, Currency):
        return currency
    try:
        return Currency(str(currency).strip().upper())
    except ValueError as error:
        raise InvalidOperationError(f"unknown currency: {currency}") from error


class Transaction:
    """One money transfer: parties, amount, fee, status, and timestamps."""

    _used_ids: set[str] = set()

    def __init__(
        self,
        sender_id: str,
        receiver_id: str,
        amount: float,
        currency: Currency | str = Currency.RUB,
        tx_type: TransactionType | str = TransactionType.INTERNAL,
        transfer_fee: float = 0.0,
        transaction_id: str | None = None,
        priority: int = 0,
        created_at: datetime | None = None,
    ) -> None:
        self.transaction_id = self._create_unique_id(transaction_id)
        self.sender_id = str(sender_id).strip()
        self.receiver_id = str(receiver_id).strip()
        if not self.sender_id:
            raise InvalidOperationError("sender is required")
        if not self.receiver_id:
            raise InvalidOperationError("receiver is required")
        self.tx_type = _resolve_type(tx_type)
        self.currency = _resolve_currency(currency)
        self.amount = _money(amount, "amount")
        self.transfer_fee = _money(transfer_fee, "transfer_fee", allow_zero=True)
        self.priority = int(priority)
        self.status = TransactionStatus.PENDING
        self.rejection_reason: str | None = None
        self.attempts = 0
        now = created_at or datetime.now()
        self.created_at = now
        self.updated_at = now
        self.processed_at: datetime | None = None

    def mark(
        self,
        status: TransactionStatus,
        *,
        reason: str | None = None,
        at: datetime | None = None,
    ) -> None:
        self.status = status
        self.rejection_reason = reason
        self.updated_at = at or datetime.now()
        if status in (
            TransactionStatus.COMPLETED,
            TransactionStatus.REJECTED,
            TransactionStatus.CANCELLED,
        ):
            self.processed_at = self.updated_at

    def __str__(self) -> str:
        fee = f" fee={self.transfer_fee:.2f}" if self.transfer_fee else ""
        reason = f" reason={self.rejection_reason}" if self.rejection_reason else ""
        return (
            f"tx {self.transaction_id}: {self.tx_type.value} "
            f"{self.amount:.2f} {self.currency.value}{fee} "
            f"{self.sender_id} -> {self.receiver_id} "
            f"[{self.status.value}]{reason}"
        )

    @classmethod
    def _create_unique_id(cls, transaction_id: str | None) -> str:
        provided = str(transaction_id).strip() if transaction_id is not None else ""
        if provided:
            if provided in cls._used_ids:
                raise ValueError(f"transaction id already exists: {provided}")
            cls._used_ids.add(provided)
            return provided
        for _ in range(32):
            short_id = uuid4().hex[:8]
            if short_id not in cls._used_ids:
                cls._used_ids.add(short_id)
                return short_id
        raise RuntimeError("could not generate a unique short transaction id")


class TransactionQueue:
    """Priority queue of pending transfers. Higher priority is processed first."""

    def __init__(self) -> None:
        self._heap: list[tuple[int, int, str]] = []
        self._items: dict[str, Transaction] = {}
        self._seq = 0

    def add(self, transaction: Transaction, priority: int | None = None) -> Transaction:
        if not isinstance(transaction, Transaction):
            raise TypeError("transaction must be a Transaction")
        if transaction.transaction_id in self._items:
            raise InvalidOperationError(
                f"transaction already queued: {transaction.transaction_id}"
            )
        if transaction.status is not TransactionStatus.PENDING:
            raise InvalidOperationError("only pending transactions can be queued")
        if priority is not None:
            transaction.priority = int(priority)
        self._seq += 1
        heapq.heappush(
            self._heap,
            (-transaction.priority, self._seq, transaction.transaction_id),
        )
        self._items[transaction.transaction_id] = transaction
        return transaction

    def pending_transactions(self) -> list[Transaction]:
        ordered = [
            self._items[tx_id]
            for _, _, tx_id in sorted(self._heap)
            if tx_id in self._items
        ]
        return [tx for tx in ordered if tx.status is TransactionStatus.PENDING]

    def cancel(self, transaction_id: str, *, at: datetime | None = None) -> Transaction:
        key = str(transaction_id).strip()
        transaction = self._items.get(key)
        if transaction is None:
            raise InvalidOperationError(f"unknown transaction: {transaction_id}")
        if transaction.status is not TransactionStatus.PENDING:
            raise InvalidOperationError(
                f"cannot cancel: transaction is {transaction.status.value}"
            )
        transaction.mark(
            TransactionStatus.CANCELLED,
            reason="cancelled by client",
            at=at,
        )
        return transaction

    def pop_next(self) -> Transaction | None:
        while self._heap:
            _, _, tx_id = heapq.heappop(self._heap)
            transaction = self._items.get(tx_id)
            if transaction is None:
                continue
            if transaction.status is TransactionStatus.PENDING:
                return transaction
        return None

    def get(self, transaction_id: str) -> Transaction | None:
        return self._items.get(str(transaction_id).strip())

    def __len__(self) -> int:
        return len(self._items)

class TransactionProcessor:
    """Applies fees, FX conversion, retries, transfer rules, and risk checks."""

    DEFAULT_OUTER_FEE_RATE = 0.01
    DEFAULT_MAX_RETRIES = 3

    def __init__(
        self,
        bank: Bank,
        queue: TransactionQueue | None = None,
        *,
        outer_fee_rate: float = DEFAULT_OUTER_FEE_RATE,
        max_retries: int = DEFAULT_MAX_RETRIES,
        clock: Callable[[], datetime] | None = None,
        audit_log: AuditLog | None = None,
        risk_analyzer: RiskAnalyzer | None = None,
    ) -> None:
        if not isinstance(bank, Bank):
            raise TypeError("bank must be a Bank instance")
        if outer_fee_rate < 0:
            raise InvalidOperationError("outer_fee_rate cannot be negative")
        if max_retries < 1:
            raise InvalidOperationError("max_retries must be at least 1")
        self.bank = bank
        self.queue = queue if queue is not None else TransactionQueue()
        self.outer_fee_rate = float(outer_fee_rate)
        self.max_retries = int(max_retries)
        self._clock = clock or datetime.now
        self.error_log: list[dict[str, object]] = []
        self.audit_log = audit_log if audit_log is not None else AuditLog(clock=self._clock)
        self.risk_analyzer = (
            risk_analyzer if risk_analyzer is not None else RiskAnalyzer()
        )
        self.reporter = AuditReporter(self.audit_log, self.risk_analyzer, self)

    def process_all(self) -> list[Transaction]:
        results: list[Transaction] = []
        while True:
            transaction = self.queue.pop_next()
            if transaction is None:
                break
            results.append(self.process(transaction))
        return results

    def process(self, transaction: Transaction) -> Transaction:
        if transaction.status is TransactionStatus.CANCELLED:
            return transaction
        if transaction.status is not TransactionStatus.PENDING:
            raise InvalidOperationError(
                f"cannot process: transaction is {transaction.status.value}"
            )

        while transaction.attempts < self.max_retries:
            transaction.attempts += 1
            transaction.mark(TransactionStatus.PROCESSING, at=self._clock())
            try:
                self._screen(transaction)
                self._apply(transaction)
                self.risk_analyzer.remember(transaction)
                transaction.mark(TransactionStatus.COMPLETED, at=self._clock())
                self.audit_log.info(
                    "transaction completed",
                    source="processor",
                    account_id=transaction.sender_id,
                    transaction_id=transaction.transaction_id,
                    extra={"receiver_id": transaction.receiver_id},
                )
                return transaction
            except (
                AccountFrozenError,
                AccountClosedError,
                InsufficientFundsError,
                InvalidOperationError,
            ) as error:
                self._log_error(transaction, error)
                transaction.mark(
                    TransactionStatus.REJECTED,
                    reason=str(error),
                    at=self._clock(),
                )
                return transaction
            except Exception as error:
                self._log_error(transaction, error)
                if transaction.attempts >= self.max_retries:
                    transaction.mark(
                        TransactionStatus.REJECTED,
                        reason=f"failed after {transaction.attempts} retries: {error}",
                        at=self._clock(),
                    )
                    return transaction
        return transaction

    def _screen(self, transaction: Transaction) -> None:
        assessment = self.risk_analyzer.assess(
            transaction, self.bank, at=self._clock()
        )
        level = LogLevel.INFO if assessment.level is RiskLevel.LOW else LogLevel.WARNING
        if assessment.level is RiskLevel.HIGH:
            level = LogLevel.CRITICAL
        self.audit_log.log(
            level,
            f"risk {assessment.level.value}: {', '.join(assessment.signals) or 'none'}",
            source="risk_analyzer",
            client_id=assessment.client_id,
            account_id=transaction.sender_id,
            transaction_id=transaction.transaction_id,
            extra={"signals": list(assessment.signals), "amount_rub": assessment.amount_rub},
        )
        if self.risk_analyzer.is_dangerous(assessment):
            raise DangerousTransactionError(
                "dangerous transaction blocked: "
                f"{assessment.level.value} risk ({', '.join(assessment.signals)})"
            )


    def _apply(self, transaction: Transaction) -> None:
        sender = self._require_account(transaction.sender_id, "sender")
        receiver: BankAccount | None = None
        if transaction.tx_type is TransactionType.INTERNAL:
            receiver = self._require_account(transaction.receiver_id, "receiver")
            if sender.account_id == receiver.account_id:
                raise InvalidOperationError("sender and receiver must be different")

        self._forbid_frozen(sender, "from")
        if sender.status is AccountStatus.CLOSED:
            raise AccountClosedError("cannot transfer: sender account is closed")
        if receiver is not None:
            self._forbid_frozen(receiver, "to")
            if receiver.status is AccountStatus.CLOSED:
                raise AccountClosedError("cannot transfer: receiver account is closed")

        debit = self._convert(transaction.amount, transaction.currency, sender.currency)
        if transaction.tx_type is TransactionType.EXTERNAL:
            transaction.transfer_fee = round(debit * self.outer_fee_rate, 2)
        fee = transaction.transfer_fee
        if (
            fee
            and sender.currency is not transaction.currency
            and transaction.tx_type is TransactionType.INTERNAL
        ):
            fee = self._convert(fee, transaction.currency, sender.currency)
            transaction.transfer_fee = fee
        total_debit = round(debit + fee, 2)
        self._forbid_negative_balance(sender, total_debit)
        credit = 0.0
        if receiver is not None:
            credit = self._convert(
                transaction.amount, transaction.currency, receiver.currency
            )

        self._debit(sender, total_debit)
        if receiver is not None:
            try:
                self._credit(receiver, credit)
            except Exception:
                self._credit(sender, total_debit)
                raise

    def _forbid_frozen(self, account: BankAccount, direction: str) -> None:
        if account.status is AccountStatus.FROZEN:
            raise AccountFrozenError(
                f"transactions {direction} frozen accounts are prohibited"
            )

    def _forbid_negative_balance(self, account: BankAccount, debit: float) -> None:
        projected = round(account.balance - debit, 2)
        if isinstance(account, SavingsAccount) and projected < account.min_balance:
            raise InsufficientFundsError(
                f"need {debit}, but balance {account.balance} cannot go below "
                f"min_balance {account.min_balance}"
            )
        if isinstance(account, PremiumAccount):
            if projected < -account.overdraft_limit:
                raise InsufficientFundsError(
                    f"need {debit}, but overdraft_limit is {account.overdraft_limit}"
                )
            return
        if projected < 0:
            raise InvalidOperationError(
                "transactions with negative balance are prohibited"
            )

    def _debit(self, account: BankAccount, amount: float) -> None:
        account._check_account_status("transfer")
        money = account._protect_from_negative(amount, allow_zero=False)
        account._balance = round(account.balance - money, 2)

    def _credit(self, account: BankAccount, amount: float) -> None:
        account.deposit(amount)

    def _convert(self, amount: float, source: Currency, target: Currency) -> float:
        if source is target:
            return round(float(amount), 2)
        rub = float(amount) * self.bank.rates_to_rub[source]
        return round(rub / self.bank.rates_to_rub[target], 2)

    def _require_account(self, account_id: str, role: str) -> BankAccount:
        try:
            return self.bank._require_account(account_id)
        except InvalidOperationError as error:
            raise InvalidOperationError(f"unknown {role}: {account_id}") from error

    def _log_error(self, transaction: Transaction, error: BaseException) -> None:
        self.error_log.append(
            {
                "transaction_id": transaction.transaction_id,
                "attempt": transaction.attempts,
                "error": type(error).__name__,
                "detail": str(error),
                "at": self._clock(),
            }
        )
        level = (
            LogLevel.CRITICAL
            if isinstance(error, DangerousTransactionError)
            else LogLevel.ERROR
        )
        self.audit_log.log(
            level,
            str(error),
            source="processor",
            account_id=transaction.sender_id,
            transaction_id=transaction.transaction_id,
            extra={"error": type(error).__name__, "attempt": transaction.attempts},
        )



