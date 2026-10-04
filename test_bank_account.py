import unittest

from abstract_account import AbstractAccount, AccountStatus, Owner
from bank_account import (
    AccountClosedError,
    AccountFrozenError,
    BankAccount,
    Currency,
    InsufficientFundsError,
    InvalidOperationError,
)


class BankAccountTests(unittest.TestCase):
    def setUp(self) -> None:
        AbstractAccount._used_ids.clear()
        self.owner = Owner("Alice Smith", email="alice@example.com", phone="+79991234567")

    def test_creates_account_with_currency_and_generated_short_id(self) -> None:
        account = BankAccount(self.owner, opening_balance=100, currency="USD")
        self.assertEqual(len(account.account_id), 8)
        self.assertEqual(account.currency, Currency.USD)
        self.assertEqual(account.status, AccountStatus.ACTIVE)
        self.assertEqual(account.get_account_info()["balance"], 100.0)

    def test_keeps_provided_account_number(self) -> None:
        account = BankAccount(self.owner, account_id="ACC-1001", currency=Currency.RUB)
        self.assertEqual(account.account_id, "ACC-1001")

    def test_empty_account_number_gets_short_uuid(self) -> None:
        account = BankAccount(self.owner, account_id="  ")
        self.assertEqual(len(account.account_id), 8)
        self.assertTrue(account.account_id.isalnum())

    def test_rejects_invalid_owner_email(self) -> None:
        with self.assertRaises(ValueError):
            BankAccount(Owner("Alice", email="not-an-email"))

    def test_rejects_invalid_currency(self) -> None:
        with self.assertRaises(ValueError):
            BankAccount(self.owner, currency="GBP")

    def test_rejects_negative_or_non_numeric_amount(self) -> None:
        account = BankAccount(self.owner, opening_balance=50)
        with self.assertRaises(InvalidOperationError):
            account.deposit(-1)
        with self.assertRaises(InvalidOperationError):
            account.deposit(0)
        with self.assertRaises(InvalidOperationError):
            account.withdraw("10")  # type: ignore[arg-type]

    def test_deposit_and_withdraw_when_active(self) -> None:
        account = BankAccount(self.owner, opening_balance=50, currency=Currency.EUR)
        account.deposit(20)
        account.withdraw(10)
        self.assertEqual(account._balance, 60.0)

    def test_cannot_withdraw_more_than_balance(self) -> None:
        account = BankAccount(self.owner, opening_balance=10)
        with self.assertRaises(InsufficientFundsError):
            account.withdraw(10.01)

    def test_frozen_account_blocks_money_operations(self) -> None:
        account = BankAccount(self.owner, opening_balance=50)
        account.freeze()
        self.assertEqual(account.status, AccountStatus.FROZEN)
        with self.assertRaises(AccountFrozenError):
            account.deposit(10)
        with self.assertRaises(AccountFrozenError):
            account.withdraw(10)

    def test_invalid_status_transitions(self) -> None:
        account = BankAccount(self.owner, opening_balance=50)
        with self.assertRaises(InvalidOperationError):
            account.unfreeze()
        account.freeze()
        with self.assertRaises(InvalidOperationError):
            account.freeze()

    def test_unfreeze_allows_operations_again(self) -> None:
        account = BankAccount(self.owner, opening_balance=50)
        account.freeze()
        account.unfreeze()
        account.deposit(5)
        self.assertEqual(account.status, AccountStatus.ACTIVE)
        self.assertEqual(account._balance, 55.0)

    def test_closed_account_blocks_operations_and_cannot_reopen(self) -> None:
        account = BankAccount(self.owner, opening_balance=50)
        account.close()
        with self.assertRaises(AccountClosedError):
            account.deposit(1)
        with self.assertRaises(AccountClosedError):
            account.withdraw(1)
        with self.assertRaises(AccountClosedError):
            account.freeze()
        with self.assertRaises(AccountClosedError):
            account.close()


if __name__ == "__main__":
    unittest.main()
