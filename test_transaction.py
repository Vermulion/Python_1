"""Unit tests for Transaction, TransactionQueue, and TransactionProcessor."""

import unittest
from datetime import datetime

from abstract_account import AbstractAccount
from bank import Bank
from client import Client, Contacts
from transaction import (
    Transaction,
    TransactionProcessor,
    TransactionQueue,
    TransactionStatus,
    TransactionType,
)


def _contacts(email: str, phone: str) -> Contacts:
    return Contacts(email=email, phones=[phone])


class TransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        AbstractAccount._used_ids.clear()
        Client._used_ids.clear()
        Transaction._used_ids.clear()
        self.now = datetime(2026, 6, 15, 12, 0)
        self.bank = Bank("Tx Bank", clock=lambda: self.now)
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
        self.carol = Client(
            first_name="Carol",
            surname="Lee",
            birth_date="1992-03-20",
            contacts=_contacts("carol@example.com", "+79993333333"),
            client_id="CL-CAROL",
        )
        self.dana = Client(
            first_name="Dana",
            surname="Kim",
            birth_date="1988-07-12",
            contacts=_contacts("dana@example.com", "+79994444444"),
            client_id="CL-DANA",
        )
        for client in (self.alice, self.bob, self.carol, self.dana):
            self.bank.add_client(client)

        self.bank.open_account(
            "CL-ALICE", "checking", opening_balance=10_000, account_id="ALICE-RUB"
        )
        self.bank.open_account(
            "CL-ALICE",
            "premium",
            opening_balance=100,
            account_id="ALICE-USD",
            currency="USD",
            overdraft_limit=50,
            fixed_fee=0,
        )
        self.bank.open_account(
            "CL-BOB",
            "savings",
            opening_balance=50,
            account_id="BOB-EUR",
            currency="EUR",
            min_balance=10,
            monthly_rate=0.01,
        )
        self.bank.open_account(
            "CL-BOB", "checking", opening_balance=500, account_id="BOB-RUB"
        )
        self.bank.open_account(
            "CL-CAROL",
            "investment",
            opening_balance=200,
            account_id="CAROL-CNY",
            currency="CNY",
        )
        self.bank.open_account(
            "CL-DANA", "checking", opening_balance=1_000, account_id="DANA-RUB"
        )
        self.bank.freeze_account("DANA-RUB")
        self.queue = TransactionQueue()
        self.processor = TransactionProcessor(
            self.bank, self.queue, outer_fee_rate=0.01, clock=lambda: self.now
        )


    def _tx(self, **kwargs) -> Transaction:
        return Transaction(**kwargs)

    def test_transaction_stores_fields_and_timestamps(self) -> None:
        tx = self._tx(
            sender_id="ALICE-RUB",
            receiver_id="BOB-RUB",
            amount=100,
            currency="RUB",
            tx_type="internal",
            transfer_fee=1.5,
            transaction_id="TX-1",
            created_at=self.now,
        )
        self.assertEqual(tx.transaction_id, "TX-1")
        self.assertEqual(tx.tx_type, TransactionType.INTERNAL)
        self.assertEqual(tx.amount, 100.0)
        self.assertEqual(tx.transfer_fee, 1.5)
        self.assertEqual(tx.status, TransactionStatus.PENDING)
        self.assertIsNone(tx.rejection_reason)
        self.assertEqual(tx.created_at, self.now)
        self.assertEqual(tx.updated_at, self.now)

    def test_queue_priority_pending_and_cancel(self) -> None:
        low = self._tx(
            sender_id="A", receiver_id="B", amount=1, transaction_id="LOW", priority=1
        )
        high = self._tx(
            sender_id="A", receiver_id="B", amount=1, transaction_id="HIGH", priority=9
        )
        mid = self._tx(
            sender_id="A", receiver_id="B", amount=1, transaction_id="MID", priority=5
        )
        self.queue.add(low)
        self.queue.add(high)
        self.queue.add(mid)
        pending = self.queue.pending_transactions()
        self.assertEqual([tx.transaction_id for tx in pending], ["HIGH", "MID", "LOW"])
        self.queue.cancel("MID")
        self.assertEqual(self.queue.get("MID").status, TransactionStatus.CANCELLED)
        self.assertEqual(
            [tx.transaction_id for tx in self.queue.pending_transactions()],
            ["HIGH", "LOW"],
        )
        self.assertEqual(self.queue.pop_next().transaction_id, "HIGH")

    def test_internal_transfer_moves_money(self) -> None:
        tx = self._tx(
            sender_id="ALICE-RUB",
            receiver_id="BOB-RUB",
            amount=100,
            transaction_id="TX-OK",
        )
        self.processor.process(tx)
        self.assertEqual(tx.status, TransactionStatus.COMPLETED)
        self.assertEqual(self.bank._require_account("ALICE-RUB").balance, 9_900)
        self.assertEqual(self.bank._require_account("BOB-RUB").balance, 600)

    def test_currency_conversion(self) -> None:
        tx = self._tx(
            sender_id="ALICE-RUB",
            receiver_id="CAROL-CNY",
            amount=90,
            currency="RUB",
            transaction_id="TX-FX",
        )
        self.processor.process(tx)
        self.assertEqual(tx.status, TransactionStatus.COMPLETED)
        self.assertEqual(self.bank._require_account("ALICE-RUB").balance, 9_910)
        self.assertEqual(self.bank._require_account("CAROL-CNY").balance, 207.2)

    def test_frozen_account_is_rejected(self) -> None:
        tx = self._tx(
            sender_id="DANA-RUB",
            receiver_id="BOB-RUB",
            amount=50,
            transaction_id="TX-FROZEN",
        )
        self.processor.process(tx)
        self.assertEqual(tx.status, TransactionStatus.REJECTED)
        self.assertIn("frozen", tx.rejection_reason)
        self.assertEqual(self.bank._require_account("DANA-RUB").balance, 1_000)
        self.assertEqual(self.processor.error_log[0]["error"], "AccountFrozenError")

    def test_negative_balance_prohibited_except_premium(self) -> None:
        poor = self._tx(
            sender_id="BOB-RUB",
            receiver_id="ALICE-RUB",
            amount=501,
            transaction_id="TX-NEG",
        )
        self.processor.process(poor)
        self.assertEqual(poor.status, TransactionStatus.REJECTED)
        self.assertIn("negative balance", poor.rejection_reason)
        self.assertEqual(self.bank._require_account("BOB-RUB").balance, 500)

        overdraft = self._tx(
            sender_id="ALICE-USD",
            receiver_id="BOB-RUB",
            amount=120,
            currency="USD",
            transaction_id="TX-PREM",
        )
        self.processor.process(overdraft)
        self.assertEqual(overdraft.status, TransactionStatus.COMPLETED)
        self.assertEqual(self.bank._require_account("ALICE-USD").balance, -20)

    def test_outer_transaction_charges_fee(self) -> None:
        tx = self._tx(
            sender_id="ALICE-RUB",
            receiver_id="SWIFT-999",
            amount=200,
            tx_type="external",
            transaction_id="TX-OUT",
        )
        self.processor.process(tx)
        self.assertEqual(tx.status, TransactionStatus.COMPLETED)
        self.assertEqual(tx.transfer_fee, 2.0)
        self.assertEqual(self.bank._require_account("ALICE-RUB").balance, 9_798)

    def test_retries_unexpected_errors_then_rejects(self) -> None:
        tx = self._tx(
            sender_id="ALICE-RUB",
            receiver_id="BOB-RUB",
            amount=10,
            transaction_id="TX-RETRY",
        )

        def boom(_transaction: Transaction) -> None:
            raise RuntimeError("temporary outage")

        self.processor._apply = boom  # type: ignore[method-assign]
        result = self.processor.process(tx)
        self.assertEqual(result.status, TransactionStatus.REJECTED)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(len(self.processor.error_log), 3)
        self.assertIn("failed after 3 retries", result.rejection_reason)

    def test_ten_transactions_queued_and_executed(self) -> None:
        specs = [
            ("T1", "ALICE-RUB", "BOB-RUB", 100, "RUB", "internal", 10),
            ("T2", "ALICE-RUB", "CAROL-CNY", 90, "RUB", "internal", 8),
            ("T3", "ALICE-USD", "BOB-RUB", 10, "USD", "internal", 7),
            ("T4", "BOB-EUR", "ALICE-RUB", 5, "EUR", "internal", 6),
            ("T5", "ALICE-RUB", "SWIFT-1", 200, "RUB", "external", 5),
            ("T6", "DANA-RUB", "BOB-RUB", 50, "RUB", "internal", 4),
            ("T7", "BOB-RUB", "ALICE-RUB", 10_000, "RUB", "internal", 3),
            ("T8", "ALICE-USD", "BOB-RUB", 130, "USD", "internal", 2),
            ("T9", "ALICE-RUB", "BOB-RUB", 50, "RUB", "internal", 1),
            ("T10", "BOB-RUB", "ALICE-RUB", 25, "RUB", "internal", 0),
        ]
        for tx_id, sender, receiver, amount, currency, tx_type, priority in specs:
            self.queue.add(
                self._tx(
                    sender_id=sender,
                    receiver_id=receiver,
                    amount=amount,
                    currency=currency,
                    tx_type=tx_type,
                    transaction_id=tx_id,
                    priority=priority,
                )
            )
        self.assertEqual(len(self.queue.pending_transactions()), 10)
        results = self.processor.process_all()
        self.assertEqual([tx.transaction_id for tx in results], [f"T{i}" for i in range(1, 11)])
        by_id = {tx.transaction_id: tx for tx in results}
        self.assertEqual(by_id["T1"].status, TransactionStatus.COMPLETED)
        self.assertEqual(by_id["T2"].status, TransactionStatus.COMPLETED)
        self.assertEqual(by_id["T3"].status, TransactionStatus.COMPLETED)
        self.assertEqual(by_id["T4"].status, TransactionStatus.COMPLETED)
        self.assertEqual(by_id["T5"].status, TransactionStatus.COMPLETED)
        self.assertEqual(by_id["T5"].transfer_fee, 2.0)
        self.assertEqual(by_id["T6"].status, TransactionStatus.REJECTED)
        self.assertIn("frozen", by_id["T6"].rejection_reason)
        self.assertEqual(by_id["T7"].status, TransactionStatus.REJECTED)
        self.assertIn("negative balance", by_id["T7"].rejection_reason)
        self.assertEqual(by_id["T8"].status, TransactionStatus.COMPLETED)
        self.assertLess(self.bank._require_account("ALICE-USD").balance, 0)
        self.assertEqual(by_id["T9"].status, TransactionStatus.COMPLETED)
        self.assertEqual(by_id["T10"].status, TransactionStatus.COMPLETED)
        self.assertEqual(len(self.queue.pending_transactions()), 0)
        self.assertTrue(self.processor.error_log)


if __name__ == "__main__":
    unittest.main()

