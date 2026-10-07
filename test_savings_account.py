import unittest

from abstract_account import AbstractAccount, AccountFrozenError, Owner
from bank_account import InsufficientFundsError, InvalidOperationError
from savings_account import SavingsAccount


class SavingsAccountTests(unittest.TestCase):
    def setUp(self) -> None:
        AbstractAccount._used_ids.clear()
        self.owner = Owner("Alice Smith", email="alice@example.com", phone="+79991234567")

    def test_stores_min_balance_and_monthly_rate(self) -> None:
        account = SavingsAccount(
            self.owner,
            opening_balance=100,
            min_balance=50,
            monthly_rate=0.01,
        )
        info = account.get_account_info()
        self.assertEqual(account.min_balance, 50.0)
        self.assertEqual(account.monthly_rate, 0.01)
        self.assertEqual(info["min_balance"], 50.0)
        self.assertEqual(info["monthly_rate"], 0.01)
        self.assertEqual(info["balance"], 100.0)

    def test_opening_balance_cannot_be_below_min_balance(self) -> None:
        with self.assertRaises(InvalidOperationError):
            SavingsAccount(self.owner, opening_balance=10, min_balance=50)

    def test_cannot_withdraw_below_min_balance(self) -> None:
        account = SavingsAccount(self.owner, opening_balance=100, min_balance=40)
        with self.assertRaises(InsufficientFundsError):
            account.withdraw(61)
        self.assertEqual(account._balance, 100)
        account.withdraw(60)
        self.assertEqual(account._balance, 40.0)

    def test_apply_monthly_interest_credits_rounded_return(self) -> None:
        account = SavingsAccount(
            self.owner,
            opening_balance=100,
            monthly_rate=0.015,
        )
        new_balance = account.apply_monthly_interest()
        self.assertEqual(new_balance, 101.5)
        self.assertEqual(account._balance, 101.5)

    def test_zero_rate_leaves_balance_unchanged(self) -> None:
        account = SavingsAccount(self.owner, opening_balance=100, monthly_rate=0)
        self.assertEqual(account.apply_monthly_interest(), 100.0)

    def test_frozen_account_cannot_apply_interest(self) -> None:
        account = SavingsAccount(self.owner, opening_balance=100, monthly_rate=0.01)
        account.freeze()
        with self.assertRaises(AccountFrozenError):
            account.apply_monthly_interest()

    def test_rejects_negative_monthly_rate(self) -> None:
        with self.assertRaises(InvalidOperationError):
            SavingsAccount(self.owner, monthly_rate=-0.01)

    def test_str_includes_min_balance_and_rate(self) -> None:
        account = SavingsAccount(
            self.owner,
            opening_balance=1000,
            account_id="SAV-3003",
            min_balance=100,
            monthly_rate=0.01,
        )
        text = str(account)
        self.assertIn("SavingsAccount", text)
        self.assertIn("Alice Smith", text)
        self.assertIn("****3003", text)
        self.assertIn("min_balance: 100.00", text)
        self.assertIn("monthly_rate: 1.00%", text)


if __name__ == "__main__":
    unittest.main()
