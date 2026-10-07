import unittest

from abstract_account import AbstractAccount, AccountFrozenError, Owner
from bank_account import InsufficientFundsError, InvalidOperationError
from premium_account import PremiumAccount


class PremiumAccountTests(unittest.TestCase):
    def setUp(self) -> None:
        AbstractAccount._used_ids.clear()
        self.owner = Owner("Dana Kim", email="dana@example.com", phone="+79994445566")

    def test_stores_increased_limits_overdraft_and_fee(self) -> None:
        account = PremiumAccount(
            self.owner,
            opening_balance=500,
            transaction_limit=50_000,
            overdraft_limit=200,
            fixed_fee=5,
        )
        info = account.get_account_info()
        self.assertEqual(info["transaction_limit"], 50_000.0)
        self.assertEqual(info["overdraft_limit"], 200.0)
        self.assertEqual(info["fixed_fee"], 5.0)
        self.assertEqual(info["available_funds"], 700.0)

    def test_withdraw_charges_fixed_fee(self) -> None:
        account = PremiumAccount(self.owner, opening_balance=100, fixed_fee=5, overdraft_limit=50)
        account.withdraw(20)
        self.assertEqual(account._balance, 75.0)

    def test_overdraft_allows_negative_balance(self) -> None:
        account = PremiumAccount(self.owner, opening_balance=10, fixed_fee=5, overdraft_limit=50)
        account.withdraw(20)
        self.assertEqual(account._balance, -15.0)

    def test_cannot_exceed_overdraft_limit(self) -> None:
        account = PremiumAccount(self.owner, opening_balance=10, fixed_fee=5, overdraft_limit=20)
        with self.assertRaises(InsufficientFundsError):
            account.withdraw(30)
        self.assertEqual(account._balance, 10)

    def test_rejects_amount_above_transaction_limit(self) -> None:
        account = PremiumAccount(
            self.owner,
            opening_balance=1_000,
            transaction_limit=100,
            fixed_fee=0,
        )
        with self.assertRaises(InvalidOperationError):
            account.withdraw(100.01)
        with self.assertRaises(InvalidOperationError):
            account.deposit(101)

    def test_frozen_account_blocks_overdraft_withdraw(self) -> None:
        account = PremiumAccount(self.owner, opening_balance=50)
        account.freeze()
        with self.assertRaises(AccountFrozenError):
            account.withdraw(10)

    def test_str_includes_limit_overdraft_and_fee(self) -> None:
        account = PremiumAccount(
            self.owner,
            opening_balance=500,
            account_id="PREM-4004",
            transaction_limit=1_000_000,
            overdraft_limit=1_000,
            fixed_fee=5,
        )
        text = str(account)
        self.assertIn("PremiumAccount", text)
        self.assertIn("Dana Kim", text)
        self.assertIn("****4004", text)
        self.assertIn("limit: 1000000.00", text)
        self.assertIn("overdraft: 1000.00", text)
        self.assertIn("fee: 5.00", text)


if __name__ == "__main__":
    unittest.main()
