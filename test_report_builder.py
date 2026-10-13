"""Unit tests for ReportBuilder: reports, export, and charts."""

import json
import os
import tempfile
import unittest
from datetime import datetime

from abstract_account import AbstractAccount
from bank import Bank
from client import Client, Contacts
from report_builder import ReportBuilder
from transaction import (
    Transaction,
    TransactionProcessor,
    TransactionQueue,
    TransactionStatus,
)


def _contacts(email: str, phone: str) -> Contacts:
    return Contacts(email=email, phones=[phone])


class ReportBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        AbstractAccount._used_ids.clear()
        Client._used_ids.clear()
        Transaction._used_ids.clear()
        self.day = datetime(2026, 6, 15, 12, 0)
        self.bank = Bank("Report Bank", clock=lambda: self.day)
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
            "CL-ALICE", "checking", opening_balance=10_000, account_id="ALICE-RUB"
        )
        self.bank.open_account(
            "CL-BOB", "checking", opening_balance=1_000, account_id="BOB-RUB"
        )
        self.queue = TransactionQueue()
        self.processor = TransactionProcessor(
            self.bank, self.queue, outer_fee_rate=0.01, clock=lambda: self.day
        )
        self.queue.add(
            Transaction(
                sender_id="ALICE-RUB",
                receiver_id="BOB-RUB",
                amount=250,
                transaction_id="RPT-OK",
                created_at=self.day,
            )
        )
        self.queue.add(
            Transaction(
                sender_id="ALICE-RUB",
                receiver_id="MISSING",
                amount=10,
                transaction_id="RPT-BAD",
                created_at=self.day,
            )
        )
        self.processor.process_all()
        self.builder = ReportBuilder(
            self.bank,
            self.processor,
            transactions=list(self.queue._items.values()),
            output_dir="reports",
        )

    def test_client_bank_and_risk_reports(self) -> None:
        client = self.builder.client_report("CL-ALICE")
        self.assertEqual(client["kind"], "client")
        self.assertEqual(client["client_id"], "CL-ALICE")
        self.assertEqual(len(client["accounts"]), 1)
        self.assertTrue(client["transactions"])
        bank = self.builder.bank_report()
        self.assertEqual(bank["kind"], "bank")
        self.assertEqual(bank["clients"], 2)
        self.assertEqual(bank["transaction_statistics"]["total"], 2)
        ranking_ids = [row["client_id"] for row in bank["ranking"]]
        self.assertEqual(ranking_ids[0], "CL-ALICE")
        risk = self.builder.risk_report()
        self.assertEqual(risk["kind"], "risk")
        self.assertIn("low", risk["by_level"])
        self.assertTrue(risk["assessments"])
        self.assertEqual(len(risk["client_profiles"]), 2)

    def test_export_txt_json_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bank = self.builder.bank_report()
            txt_path = self.builder.export_to_txt(os.path.join(tmp, "bank.txt"), bank)
            json_path = self.builder.export_to_json(os.path.join(tmp, "bank.json"), bank)
            csv_path = self.builder.export_to_csv(os.path.join(tmp, "bank.csv"), bank)
            with open(txt_path, encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("BANK REPORT", text)
            self.assertIn("Alice Smith", text)
            with open(json_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["kind"], "bank")
            self.assertEqual(payload["bank_name"], "Report Bank")
            with open(csv_path, encoding="utf-8") as handle:
                header = handle.readline()
                body = handle.read()
            self.assertIn("client_id", header)
            self.assertIn("CL-ALICE", body)
            client = self.builder.client_report("CL-ALICE")
            csv_client = self.builder.export_to_csv(
                os.path.join(tmp, "client.csv"), client
            )
            with open(csv_client, encoding="utf-8") as handle:
                client_csv = handle.read()
            self.assertIn("RPT-OK", client_csv)

    def test_save_charts_and_export_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            charts = self.builder.save_charts(os.path.join(tmp, "charts"))
            self.assertIn("pie_status", charts)
            self.assertIn("bar_balances", charts)
            self.assertIn("balance_movement", charts)
            for path in charts.values():
                self.assertTrue(os.path.isfile(path), path)
                self.assertGreater(os.path.getsize(path), 0)
            paths = self.builder.export_all(os.path.join(tmp, "all"))
            self.assertTrue(os.path.isfile(paths["bank_json"]))
            self.assertTrue(os.path.isfile(paths["risk_csv"]))
            self.assertTrue(os.path.isfile(paths["client_txt"]))
            self.assertTrue(os.path.isfile(paths["pie_risk"]))

    def test_balance_series_ends_at_current_total(self) -> None:
        series = self.builder.balance_series()
        self.assertGreaterEqual(len(series), 1)
        self.assertAlmostEqual(series[-1][1], self.bank.get_total_balance())
        alice = self.builder.balance_series("CL-ALICE")
        self.assertAlmostEqual(alice[-1][1], self.bank.get_total_balance("CL-ALICE"))
        completed = [
            tx
            for tx in self.builder.transactions
            if tx.status is TransactionStatus.COMPLETED
        ]
        self.assertTrue(completed)


if __name__ == "__main__":
    unittest.main()

