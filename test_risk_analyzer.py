"""Unit tests for RiskAnalyzer, blocking, and audit reports."""

import unittest
from datetime import datetime, timedelta

from abstract_account import AbstractAccount
from bank import Bank
from client import Client, Contacts
from risk_analyzer import (
    SIGNAL_FREQUENT,
    SIGNAL_LARGE_SUM,
    SIGNAL_NEW_ACCOUNT,
    SIGNAL_NIGHT,
    RiskAnalyzer,
    RiskLevel,
)
from transaction import (
    Transaction,
    TransactionProcessor,
    TransactionQueue,
    TransactionStatus,
)


def _contacts(email: str, phone: str) -> Contacts:
    return Contacts(email=email, phones=[phone])


class RiskAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        AbstractAccount._used_ids.clear()
        Client._used_ids.clear()
        Transaction._used_ids.clear()
        self.day = datetime(2026, 6, 15, 12, 0)
        self.night = datetime(2026, 6, 15, 2, 0)
        self.bank = Bank("Risk Bank", clock=lambda: self.day)
        self.alice = Client(
            first_name="Alice",
            surname="Smith",
            birth_date="1990-01-15",
            contacts=_contacts("alice@example.com", "+79991111111"),
            client_id="CL-ALICE",
        )
        self.bob = Client(
            first_name="Bob",
            surname="Jones",
            birth_date="1985-05-05",
            contacts=_contacts("bob@example.com", "+79992222222"),
            client_id="CL-BOB",
        )
        self.bank.add_client(self.alice)
        self.bank.add_client(self.bob)
        self.bank.open_account(
            "CL-ALICE", "checking", opening_balance=200_000, account_id="ALICE-RUB"
        )
        self.bank.open_account(
            "CL-BOB", "checking", opening_balance=5_000, account_id="BOB-RUB"
        )
        self.queue = TransactionQueue()
        self.analyzer = RiskAnalyzer(large_sum_rub=50_000, frequent_limit=3)
        self.processor = TransactionProcessor(
            self.bank,
            self.queue,
            outer_fee_rate=0.01,
            clock=lambda: self.day,
            risk_analyzer=self.analyzer,
        )

    def _tx(self, **kwargs) -> Transaction:
        return Transaction(**kwargs)

    def test_new_small_daytime_transfer_is_low_risk(self) -> None:
        tx = self._tx(
            sender_id="ALICE-RUB",
            receiver_id="BOB-RUB",
            amount=100,
            transaction_id="R-LOW",
            created_at=self.day,
        )
        assessment = self.analyzer.assess(tx, self.bank, at=self.day)
        self.assertEqual(assessment.level, RiskLevel.LOW)
        self.assertEqual(assessment.signals, [SIGNAL_NEW_ACCOUNT])

    def test_large_sum_and_new_account_is_middle_risk(self) -> None:
        tx = self._tx(
            sender_id="ALICE-RUB",
            receiver_id="BOB-RUB",
            amount=60_000,
            transaction_id="R-MID",
            created_at=self.day,
        )
        assessment = self.analyzer.assess(tx, self.bank, at=self.day)
        self.assertEqual(assessment.level, RiskLevel.MIDDLE)
        self.assertIn(SIGNAL_LARGE_SUM, assessment.signals)
        self.assertIn(SIGNAL_NEW_ACCOUNT, assessment.signals)


    def test_night_large_new_transfer_is_high_risk(self) -> None:
        tx = self._tx(
            sender_id="ALICE-RUB",
            receiver_id="BOB-RUB",
            amount=60_000,
            transaction_id="R-HIGH",
            created_at=self.night,
        )
        assessment = self.analyzer.assess(tx, self.bank, at=self.night)
        self.assertEqual(assessment.level, RiskLevel.HIGH)
        self.assertEqual(
            set(assessment.signals),
            {SIGNAL_LARGE_SUM, SIGNAL_NEW_ACCOUNT, SIGNAL_NIGHT},
        )

    def test_frequent_transactions_raise_risk(self) -> None:
        for index in range(3):
            tx = self._tx(
                sender_id="ALICE-RUB",
                receiver_id="BOB-RUB",
                amount=10,
                transaction_id=f"R-F{index}",
                created_at=self.day + timedelta(minutes=index),
            )
            assessment = self.analyzer.assess(
                tx, self.bank, at=self.day + timedelta(minutes=index)
            )
        self.assertIn(SIGNAL_FREQUENT, assessment.signals)

    def test_processor_blocks_dangerous_transaction(self) -> None:
        night_processor = TransactionProcessor(
            self.bank,
            TransactionQueue(),
            clock=lambda: self.night,
            risk_analyzer=RiskAnalyzer(large_sum_rub=50_000),
        )
        tx = self._tx(
            sender_id="ALICE-RUB",
            receiver_id="UNKNOWN-NEW",
            amount=80_000,
            tx_type="external",
            transaction_id="R-BLOCK",
            created_at=self.night,
        )
        result = night_processor.process(tx)
        self.assertEqual(result.status, TransactionStatus.REJECTED)
        self.assertIn("dangerous transaction blocked", result.rejection_reason)
        self.assertEqual(self.bank._require_account("ALICE-RUB").balance, 200_000)

    def test_ordinary_and_suspicious_set(self) -> None:
        analyzer = RiskAnalyzer(large_sum_rub=50_000, frequent_limit=4)
        processor = TransactionProcessor(
            self.bank,
            self.queue,
            clock=lambda: self.day,
            risk_analyzer=analyzer,
        )
        ordinary = [
            ("O1", "ALICE-RUB", "BOB-RUB", 50, "internal", self.day, 5),
            ("O2", "ALICE-RUB", "BOB-RUB", 75, "internal", self.day, 4),
            ("O3", "BOB-RUB", "ALICE-RUB", 20, "internal", self.day, 3),
        ]
        for tx_id, sender, receiver, amount, tx_type, created, priority in ordinary:
            self.queue.add(
                self._tx(
                    sender_id=sender,
                    receiver_id=receiver,
                    amount=amount,
                    tx_type=tx_type,
                    transaction_id=tx_id,
                    priority=priority,
                    created_at=created,
                )
            )
        results = processor.process_all()
        self.assertTrue(all(tx.status is TransactionStatus.COMPLETED for tx in results))

        night_queue = TransactionQueue()
        night_processor = TransactionProcessor(
            self.bank,
            night_queue,
            clock=lambda: self.night,
            risk_analyzer=analyzer,
            audit_log=processor.audit_log,
        )
        suspicious = [
            ("S1", "ALICE-RUB", "SWIFT-NEW", 80_000, "external", self.night, 9),
            ("S2", "ALICE-RUB", "GHOST-ACC", 70_000, "external", self.night, 8),
        ]
        for tx_id, sender, receiver, amount, tx_type, created, priority in suspicious:
            night_queue.add(
                self._tx(
                    sender_id=sender,
                    receiver_id=receiver,
                    amount=amount,
                    tx_type=tx_type,
                    transaction_id=tx_id,
                    priority=priority,
                    created_at=created,
                )
            )
        blocked = night_processor.process_all()
        self.assertTrue(all(tx.status is TransactionStatus.REJECTED for tx in blocked))

        report = night_processor.reporter
        flagged = report.suspicious_transactions()
        self.assertTrue(any(row["transaction_id"] == "S1" for row in flagged))
        profile = report.client_risk_profile("CL-ALICE")
        self.assertEqual(profile["risk_level"], RiskLevel.HIGH.value)
        self.assertIn("S1", profile["suspicious_transactions"])
        stats = report.error_statistics()
        self.assertGreaterEqual(stats["total"], 2)
        self.assertIn("DangerousTransactionError", stats["by_error"])
        self.assertTrue(night_processor.audit_log.filter(min_level="CRITICAL"))


if __name__ == "__main__":
    unittest.main()

