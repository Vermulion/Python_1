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

    def test_sum_stays_correct_with_cents(self) -> None:
        account = BankAccount(self.owner, opening_balance=10.10, currency=Currency.RUB)
        account.deposit(0.20)
        self.assertEqual(account._balance, 10.30)
        account.withdraw(0.05)
        self.assertEqual(account._balance, 10.25)

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

    def test_str_shows_type_client_last_four_status_balance_currency(self) -> None:
        account = BankAccount(
            self.owner,
            opening_balance=100,
            account_id="ACC-1001",
            currency=Currency.USD,
        )
        text = str(account)
        self.assertIn("BankAccount", text)
        self.assertIn("Alice Smith", text)
        self.assertIn("****1001", text)
        self.assertNotIn("ACC-", text)
        self.assertIn("active", text)
        self.assertIn("100.00 USD", text)


if __name__ == "__main__":
    unittest.main()
