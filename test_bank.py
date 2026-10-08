import unittest
from datetime import datetime

from abstract_account import AbstractAccount, AccountStatus
from bank import Bank
from bank_account import BankAccount, InvalidOperationError
from client import Client, ClientStatus, Contacts
from investment_account import InvestmentAccount
from premium_account import PremiumAccount
from savings_account import SavingsAccount


class BankTests(unittest.TestCase):
    def setUp(self) -> None:
        AbstractAccount._used_ids.clear()
        Client._used_ids.clear()
        self.bank = Bank("Study Bank", clock=lambda: datetime(2026, 6, 15, 12, 0))
        self.alice = Client(
            first_name="Alice",
            surname="Smith",
            middle_name="Marie",
            birth_date="1990-01-15",
            contacts=Contacts(
                email="alice@example.com",
                phones=["+79991234567"],
                address="Moscow",
            ),
            client_id="CL-1",
        )
        self.bob = Client(
            first_name="Bob",
            surname="Jones",
            birth_date="1985-05-05",
            contacts=Contacts(
                email="bob@example.com",
                phones=["+79997654321"],
            ),
            client_id="CL-2",
        )
        self.bank.add_client(self.alice)
        self.bank.add_client(self.bob)

    def test_add_client_rejects_duplicates(self) -> None:
        with self.assertRaises(InvalidOperationError):
            self.bank.add_client(self.alice)

    def test_authenticate_client(self) -> None:
        found = self.bank.authenticate_client("CL-1", "alice@example.com")
        self.assertIs(found, self.alice)
        with self.assertRaises(InvalidOperationError):
            self.bank.authenticate_client("CL-1", "wrong@example.com")
        with self.assertRaises(InvalidOperationError):
            self.bank.authenticate_client("missing", "alice@example.com")

    def test_blocked_client_cannot_authenticate(self) -> None:
        self.alice.status = ClientStatus.BLOCKED
        with self.assertRaises(InvalidOperationError):
            self.bank.authenticate_client("CL-1", "alice@example.com")

    def test_open_account_for_each_type(self) -> None:
        checking = self.bank.open_account("CL-1", "checking", opening_balance=100, account_id="ACC-1")
        savings = self.bank.open_account(
            "CL-1",
            "savings",
            opening_balance=200,
            account_id="SAV-1",
            min_balance=50,
            monthly_rate=0.01,
        )
        premium = self.bank.open_account("CL-2", "premium", opening_balance=300, account_id="PREM-1")
        investment = self.bank.open_account(
            "CL-2",
            "investment",
            opening_balance=400,
            account_id="INV-1",
        )
        self.assertIsInstance(checking, BankAccount)
        self.assertIsInstance(savings, SavingsAccount)
        self.assertIsInstance(premium, PremiumAccount)
        self.assertIsInstance(investment, InvestmentAccount)
        self.assertEqual(len(self.alice.accounts), 2)
        self.assertEqual(len(self.bob.accounts), 2)

    def test_freeze_unfreeze_and_close_account(self) -> None:
        account = self.bank.open_account("CL-1", opening_balance=50, account_id="ACC-9")
        self.bank.freeze_account("ACC-9")
        self.assertEqual(account.status, AccountStatus.FROZEN)
        self.bank.unfreeze_account("ACC-9")
        self.assertEqual(account.status, AccountStatus.ACTIVE)
        self.bank.close_account("ACC-9")
        self.assertEqual(account.status, AccountStatus.CLOSED)

    def test_search_accounts_by_client_status_and_type(self) -> None:
        self.bank.open_account("CL-1", "checking", account_id="ACC-1")
        savings = self.bank.open_account("CL-1", "savings", opening_balance=100, account_id="SAV-1")
        self.bank.open_account("CL-2", "premium", account_id="PREM-1")
        self.bank.freeze_account("SAV-1")

        by_id = self.bank.search_accounts(account_id="ACC-1")
        self.assertEqual([item.account_id for item in by_id], ["ACC-1"])

        alice_accounts = self.bank.search_accounts(client_id="CL-1")
        self.assertEqual({item.account_id for item in alice_accounts}, {"ACC-1", "SAV-1"})

        frozen = self.bank.search_accounts(status="frozen")
        self.assertEqual(frozen, [savings])

        premiums = self.bank.search_accounts(account_type="premium")
        self.assertEqual([item.account_id for item in premiums], ["PREM-1"])

    def test_unknown_account_operations_fail(self) -> None:
        with self.assertRaises(InvalidOperationError):
            self.bank.freeze_account("missing")
        with self.assertRaises(InvalidOperationError):
            self.bank.open_account("CL-1", "crypto")

    def test_three_failed_auth_attempts_block_client(self) -> None:
        for _ in range(2):
            with self.assertRaises(InvalidOperationError):
                self.bank.authenticate_client("CL-1", "wrong@example.com")
            self.assertEqual(self.alice.status, ClientStatus.ACTIVE)

        with self.assertRaises(InvalidOperationError):
            self.bank.authenticate_client("CL-1", "wrong@example.com")

        self.assertEqual(self.alice.status, ClientStatus.BLOCKED)
        self.assertEqual(self.alice.failed_auth_attempts, 3)
        self.assertIn("auth_locked", self.alice.tags)
        tags = [event["tag"] for event in self.bank.suspicious_events]
        self.assertEqual(tags.count("failed_auth"), 3)
        self.assertIn("auth_locked", tags)
        with self.assertRaises(InvalidOperationError):
            self.bank.authenticate_client("CL-1", "alice@example.com")

    def test_successful_auth_resets_failed_attempts(self) -> None:
        with self.assertRaises(InvalidOperationError):
            self.bank.authenticate_client("CL-1", "wrong@example.com")
        self.assertEqual(self.alice.failed_auth_attempts, 1)
        self.bank.authenticate_client("CL-1", "alice@example.com")
        self.assertEqual(self.alice.failed_auth_attempts, 0)

    def test_night_operations_are_blocked_and_tagged(self) -> None:
        night_bank = Bank("Night Bank", clock=lambda: datetime(2026, 1, 1, 2, 30))
        night_bank.add_client(self.alice)
        with self.assertRaises(InvalidOperationError) as error:
            night_bank.open_account("CL-1", opening_balance=10, account_id="NIGHT-1")
        self.assertIn("00:00", str(error.exception))
        self.assertIn("night_operation", self.alice.tags)
        self.assertEqual(night_bank.suspicious_events[0]["tag"], "night_operation")

        day_bank = Bank("Day Bank", clock=lambda: datetime(2026, 1, 1, 9, 0))
        day_bank.add_client(self.bob)
        account = day_bank.open_account("CL-2", opening_balance=10, account_id="DAY-1")
        self.assertEqual(account.status, AccountStatus.ACTIVE)

    def test_total_balance_converts_currencies_and_skips_closed(self) -> None:
        self.bank.open_account(
            "CL-1", "checking", opening_balance=100, account_id="RUB-1", currency="RUB"
        )
        self.bank.open_account(
            "CL-1", "checking", opening_balance=10, account_id="USD-1", currency="USD"
        )
        closed = self.bank.open_account(
            "CL-1", "checking", opening_balance=50, account_id="EUR-1", currency="EUR"
        )
        self.bank.close_account("EUR-1")
        self.assertEqual(closed.status, AccountStatus.CLOSED)
        # 100 RUB + 10 USD * 90 = 1000 RUB
        self.assertEqual(self.bank.get_total_balance("CL-1"), 1000.0)
        self.assertEqual(self.bank.get_total_balance("CL-1", in_currency="USD"), round(1000 / 90, 2))

    def test_clients_ranking_orders_by_converted_total(self) -> None:
        self.bank.open_account(
            "CL-1", "checking", opening_balance=100, account_id="A-RUB", currency="RUB"
        )
        self.bank.open_account(
            "CL-2", "premium", opening_balance=20, account_id="B-USD", currency="USD"
        )
        ranking = self.bank.get_clients_ranking()
        self.assertEqual([row["client_id"] for row in ranking], ["CL-2", "CL-1"])
        self.assertEqual(ranking[0]["total_balance"], 1800.0)
        self.assertEqual(ranking[1]["total_balance"], 100.0)


if __name__ == "__main__":
    unittest.main()
