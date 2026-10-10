"""Suspicious-transaction detection, risk levels, and audit reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

from abstract_account import InvalidOperationError
from bank import NIGHT_END, NIGHT_START

if TYPE_CHECKING:
    from audit_log import AuditLog
    from bank import Bank
    from transaction import Transaction, TransactionProcessor


SIGNAL_LARGE_SUM = "large_sum"
SIGNAL_FREQUENT = "frequent_transactions"
SIGNAL_NEW_ACCOUNT = "new_account"
SIGNAL_NIGHT = "night_transaction"


class RiskLevel(Enum):
    LOW = "low"
    MIDDLE = "middle"
    HIGH = "high"


class DangerousTransactionError(InvalidOperationError):
    """Raised when the bank blocks a high-risk transfer."""


def _rank(level: RiskLevel) -> int:
    return {RiskLevel.LOW: 1, RiskLevel.MIDDLE: 2, RiskLevel.HIGH: 3}[level]


@dataclass
class RiskAssessment:
    transaction_id: str
    sender_id: str
    receiver_id: str
    client_id: str | None
    level: RiskLevel
    signals: list[str]
    amount_rub: float
    at: datetime
    extra: dict[str, object] = field(default_factory=dict)


class RiskAnalyzer:
    """Score transfers for large sums, bursts, new counterparties, and night time."""

    DEFAULT_LARGE_SUM_RUB = 50_000.0
    DEFAULT_FREQUENT_LIMIT = 5
    DEFAULT_FREQUENT_WINDOW = timedelta(hours=1)

    def __init__(
        self,
        *,
        large_sum_rub: float = DEFAULT_LARGE_SUM_RUB,
        frequent_limit: int = DEFAULT_FREQUENT_LIMIT,
        frequent_window: timedelta = DEFAULT_FREQUENT_WINDOW,
    ) -> None:
        if large_sum_rub <= 0:
            raise InvalidOperationError("large_sum_rub must be greater than 0")
        if frequent_limit < 2:
            raise InvalidOperationError("frequent_limit must be at least 2")
        self.large_sum_rub = float(large_sum_rub)
        self.frequent_limit = int(frequent_limit)
        self.frequent_window = frequent_window
        self.assessments: list[RiskAssessment] = []
        self._known_pairs: set[tuple[str, str]] = set()
        self._sender_times: list[tuple[datetime, str]] = []

    def assess(
        self,
        transaction: Transaction,
        bank: Bank,
        *,
        at: datetime | None = None,
    ) -> RiskAssessment:
        moment = at or transaction.created_at
        amount_rub = self._amount_rub(transaction, bank)
        signals: list[str] = []
        extra: dict[str, object] = {"amount_rub": amount_rub}

        if amount_rub >= self.large_sum_rub:
            signals.append(SIGNAL_LARGE_SUM)
        if self._is_frequent(transaction.sender_id, moment):
            signals.append(SIGNAL_FREQUENT)
        if (transaction.sender_id, transaction.receiver_id) not in self._known_pairs:
            signals.append(SIGNAL_NEW_ACCOUNT)
        if self._is_night(moment):
            signals.append(SIGNAL_NIGHT)

        level = self._level_for(len(signals))
        client_id = None
        try:
            sender = bank._require_account(transaction.sender_id)
            client_id = bank._client_id_for_account(sender)
        except InvalidOperationError:
            client_id = None

        assessment = RiskAssessment(
            transaction_id=transaction.transaction_id,
            sender_id=transaction.sender_id,
            receiver_id=transaction.receiver_id,
            client_id=client_id,
            level=level,
            signals=signals,
            amount_rub=amount_rub,
            at=moment,
            extra=extra,
        )
        self.assessments.append(assessment)
        self._sender_times.append((moment, transaction.sender_id))
        return assessment


    def remember(self, transaction: Transaction) -> None:
        """Mark a completed pair so later transfers to the same account are known."""
        self._known_pairs.add((transaction.sender_id, transaction.receiver_id))

    def is_dangerous(self, assessment: RiskAssessment) -> bool:
        return assessment.level is RiskLevel.HIGH

    def suspicious_transactions(
        self,
        *,
        min_level: RiskLevel = RiskLevel.MIDDLE,
    ) -> list[RiskAssessment]:
        floor = _rank(min_level)
        return [item for item in self.assessments if _rank(item.level) >= floor]

    def client_assessments(self, client_id: str) -> list[RiskAssessment]:
        return [item for item in self.assessments if item.client_id == client_id]

    def _amount_rub(self, transaction: Transaction, bank: Bank) -> float:
        rate = bank.rates_to_rub.get(transaction.currency, 1.0)
        return round(float(transaction.amount) * rate, 2)

    def _is_frequent(self, sender_id: str, at: datetime) -> bool:
        start = at - self.frequent_window
        recent = sum(
            1
            for moment, sender in self._sender_times
            if sender == sender_id and start <= moment <= at
        )
        return recent + 1 >= self.frequent_limit

    @staticmethod
    def _is_night(moment: datetime) -> bool:
        clock = moment.time()
        return NIGHT_START <= clock < NIGHT_END

    @staticmethod
    def _level_for(signal_count: int) -> RiskLevel:
        if signal_count >= 3:
            return RiskLevel.HIGH
        if signal_count == 2:
            return RiskLevel.MIDDLE
        return RiskLevel.LOW


class AuditReporter:
    """Build audit reports from the log, risk history, and processor errors."""

    def __init__(
        self,
        audit_log: AuditLog,
        analyzer: RiskAnalyzer,
        processor: TransactionProcessor | None = None,
    ) -> None:
        self.audit_log = audit_log
        self.analyzer = analyzer
        self.processor = processor

    def suspicious_transactions(
        self,
        *,
        min_level: RiskLevel = RiskLevel.MIDDLE,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for item in self.analyzer.suspicious_transactions(min_level=min_level):
            rows.append(
                {
                    "transaction_id": item.transaction_id,
                    "client_id": item.client_id,
                    "sender_id": item.sender_id,
                    "receiver_id": item.receiver_id,
                    "risk_level": item.level.value,
                    "signals": list(item.signals),
                    "amount_rub": item.amount_rub,
                    "at": item.at,
                }
            )
        return rows

    def client_risk_profile(self, client_id: str) -> dict[str, object]:
        items = self.analyzer.client_assessments(client_id)
        by_level = {level.value: 0 for level in RiskLevel}
        signals: list[str] = []
        overall = RiskLevel.LOW
        for item in items:
            by_level[item.level.value] += 1
            if _rank(item.level) > _rank(overall):
                overall = item.level
            for signal in item.signals:
                if signal not in signals:
                    signals.append(signal)
        tags: list[str] = []
        if self.processor is not None:
            try:
                tags = list(self.processor.bank._require_client(client_id).tags)
            except InvalidOperationError:
                tags = []
        return {
            "client_id": client_id,
            "risk_level": overall.value,
            "transaction_count": len(items),
            "by_level": by_level,
            "signals": signals,
            "suspicious_transactions": [
                item.transaction_id
                for item in items
                if item.level is not RiskLevel.LOW
            ],
            "tags": tags,
        }

    def error_statistics(self) -> dict[str, object]:
        rows = list(self.processor.error_log) if self.processor is not None else []
        by_error: dict[str, int] = {}
        by_transaction: dict[str, int] = {}
        for row in rows:
            name = str(row.get("error", "unknown"))
            tx_id = str(row.get("transaction_id", "unknown"))
            by_error[name] = by_error.get(name, 0) + 1
            by_transaction[tx_id] = by_transaction.get(tx_id, 0) + 1
        audit_errors = self.audit_log.filter(min_level="ERROR")
        return {
            "total": len(rows),
            "by_error": by_error,
            "by_transaction": by_transaction,
            "audit_error_count": len(audit_errors),
        }

