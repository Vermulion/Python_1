"""Integration scenario: several clients, currencies, auth, freeze, ranking."""

import unittest
from datetime import datetime

from abstract_account import AbstractAccount, AccountFrozenError, AccountStatus
from bank import Bank
from bank_account import InvalidOperationError
from client import Client, ClientStatus, Contacts
from investment_account import InvestmentAccount
from premium_account import PremiumAccount
from savings_account import SavingsAccount


def _contacts(email: str, phone: str, address: str = "") -> Contacts:
    return Contacts(email=email, phones=[phone], address=address)


class BankScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        AbstractAccount._used_ids.clear()
        Client._used_ids.clear()
        self.bank = Bank("Scenario Bank", clock=lambda: datetime(2026, 6, 15, 11, 0))

        self.alice = Client(
            first_name="Alice",
            middle_name="Marie",
            surname="Smith",
            birth_date="1990-01-15",
            contacts=_contacts("alice@example.com", "+79991111111", "Moscow"),
            client_id="CL-ALICE",
        )
        self.bob = Client(
            first_name="Bob",
            surname="Jones",
            birth_date="1985-05-05",
            contacts=_contacts("bob@example.com", "+79992222222", "Kazan"),
            client_id="CL-BOB",
        )
        self.carol = Client(
            first_name="Carol",
            surname="Lee",
            birth_date="1992-03-20",
            contacts=_contacts("carol@example.com", "+79993333333", "Sochi"),
            client_id="CL-CAROL",
        )
        for client in (self.alice, self.bob, self.carol):
            self.bank.add_client(client)

    def test_multi_client_accounts_auth_freeze_and_ranking(self) -> None:
        alice_rub = self.bank.open_account(
            "CL-ALICE",
            "checking",
            opening_balance=10_000,
            account_id="ALICE-RUB",
            currency="RUB",
        )
        alice_usd = self.bank.open_account(
            "CL-ALICE",
            "premium",
            opening_balance=100,
            account_id="ALICE-USD",
            currency="USD",
        )
        bob_eur = self.bank.open_account(
            "CL-BOB",
            "savings",
            opening_balance=50,
            account_id="BOB-EUR",
            currency="EUR",
            min_balance=10,
            monthly_rate=0.01,
        )
        carol_inv = self.bank.open_account(
            "CL-CAROL",
            "investment",
            opening_balance=200,
            account_id="CAROL-CNY",
            currency="CNY",
        )

        self.assertIsInstance(alice_usd, PremiumAccount)
        self.assertIsInstance(bob_eur, SavingsAccount)
        self.assertIsInstance(carol_inv, InvestmentAccount)

        self.assertIs(self.bank.authenticate_client("CL-ALICE", "alice@example.com"), self.alice)

        with self.assertRaises(InvalidOperationError):
            self.bank.authenticate_client("CL-BOB", "wrong@example.com")
        with self.assertRaises(InvalidOperationError):
            self.bank.authenticate_client("CL-BOB", "still-wrong@example.com")
        self.assertEqual(self.bob.status, ClientStatus.ACTIVE)
        with self.assertRaises(InvalidOperationError):
            self.bank.authenticate_client("CL-BOB", "nope@example.com")
        self.assertEqual(self.bob.status, ClientStatus.BLOCKED)
        self.assertIn("auth_locked", self.bob.tags)

        self.bank.freeze_account("ALICE-USD")
        self.assertEqual(alice_usd.status, AccountStatus.FROZEN)
        with self.assertRaises(AccountFrozenError):
            alice_usd.withdraw(10)

        frozen = self.bank.search_accounts(status="frozen")
        self.assertEqual([item.account_id for item in frozen], ["ALICE-USD"])

        self.bank.unfreeze_account("ALICE-USD")
        alice_usd.withdraw(10)
        self.assertEqual(alice_usd.balance, 85.0)  # 100 - 10 - fee 5

        carol_inv.invest("stocks", 80)
        self.assertEqual(carol_inv.balance, 120.0)

        # Alice: 10000 RUB + 85 USD * 90 = 17650
        # Bob: 50 EUR * 100 = 5000
        # Carol: (120 cash + 80 stocks) CNY * 12.5 = 2500
        self.assertEqual(self.bank.get_total_balance("CL-ALICE"), 17650.0)
        self.assertEqual(self.bank.get_total_balance("CL-BOB"), 5000.0)
        self.assertEqual(self.bank.get_total_balance("CL-CAROL"), 2500.0)

        ranking = self.bank.get_clients_ranking()
        self.assertEqual(
            [row["client_id"] for row in ranking],
            ["CL-ALICE", "CL-BOB", "CL-CAROL"],
        )
        self.assertEqual(ranking[1]["status"], "blocked")
        self.assertIn("auth_locked", ranking[1]["tags"])

        night_bank = Bank("Night", clock=lambda: datetime(2026, 6, 15, 0, 15))
        night_bank.add_client(self.carol)
        with self.assertRaises(InvalidOperationError):
            night_bank.freeze_account("CAROL-CNY")
        self.assertIn("night_operation", self.carol.tags)
        self.assertEqual(alice_rub.status, AccountStatus.ACTIVE)


if __name__ == "__main__":
    unittest.main()
