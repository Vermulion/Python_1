import unittest

from abstract_account import AbstractAccount, AccountFrozenError, Owner
from bank_account import InsufficientFundsError, InvalidOperationError
from investment_account import DEMO_GROWTH_RATES, InvestmentAccount, SecurityType


class InvestmentAccountTests(unittest.TestCase):
    def setUp(self) -> None:
        AbstractAccount._used_ids.clear()
        self.owner = Owner("Evan Wu", email="evan@example.com", phone="+79997778899")

    def test_portfolio_starts_empty(self) -> None:
        account = InvestmentAccount(self.owner, opening_balance=800)
        self.assertEqual(
            account.portfolio,
            {"stocks": 0.0, "bonds": 0.0, "etf": 0.0},
        )
        self.assertEqual(account.get_account_info()["portfolio_total"], 0.0)

    def test_invest_distributes_funds_among_security_types(self) -> None:
        account = InvestmentAccount(self.owner, opening_balance=800)
        account.invest(SecurityType.STOCKS, 300)
        account.invest("bonds", 200)
        account.invest("ETF", 100)
        self.assertEqual(account._balance, 200.0)
        self.assertEqual(account.portfolio["stocks"], 300.0)
        self.assertEqual(account.portfolio["bonds"], 200.0)
        self.assertEqual(account.portfolio["etf"], 100.0)

    def test_project_yearly_growth_with_demo_rates(self) -> None:
        account = InvestmentAccount(self.owner, opening_balance=1000)
        account.invest("stocks", 300)
        account.invest("bonds", 200)
        account.invest("etf", 100)
        growth = account.project_yearly_growth(DEMO_GROWTH_RATES)
        self.assertEqual(growth, 45.0)

    def test_rejects_unknown_security_type(self) -> None:
        account = InvestmentAccount(self.owner, opening_balance=100)
        with self.assertRaises(InvalidOperationError):
            account.invest("crypto", 10)

    def test_rejects_non_positive_invest_amount(self) -> None:
        account = InvestmentAccount(self.owner, opening_balance=100)
        with self.assertRaises(InvalidOperationError):
            account.invest("stocks", 0)
        with self.assertRaises(InvalidOperationError):
            account.invest("stocks", -1)

    def test_rejects_invest_when_funds_are_insufficient(self) -> None:
        account = InvestmentAccount(self.owner, opening_balance=50)
        with self.assertRaises(InsufficientFundsError):
            account.invest("bonds", 50.01)
        self.assertEqual(account.portfolio["bonds"], 0.0)
        self.assertEqual(account._balance, 50)

    def test_frozen_account_cannot_invest(self) -> None:
        account = InvestmentAccount(self.owner, opening_balance=100)
        account.freeze()
        with self.assertRaises(AccountFrozenError):
            account.invest("etf", 10)

    def test_withdraw_takes_cash_only(self) -> None:
        account = InvestmentAccount(self.owner, opening_balance=800)
        account.invest("stocks", 300)
        account.withdraw(100)
        self.assertEqual(account._balance, 400.0)
        self.assertEqual(account.portfolio["stocks"], 300.0)

    def test_cannot_withdraw_invested_portfolio(self) -> None:
        account = InvestmentAccount(self.owner, opening_balance=800)
        account.invest("bonds", 500)
        with self.assertRaises(InsufficientFundsError):
            account.withdraw(300.01)
        self.assertEqual(account._balance, 300.0)
        self.assertEqual(account.portfolio["bonds"], 500.0)

    def test_frozen_account_cannot_withdraw(self) -> None:
        account = InvestmentAccount(self.owner, opening_balance=100)
        account.freeze()
        with self.assertRaises(AccountFrozenError):
            account.withdraw(10)

    def test_growth_rates_must_be_a_dictionary_with_needed_types(self) -> None:
        account = InvestmentAccount(self.owner, opening_balance=100)
        account.invest("stocks", 50)
        with self.assertRaises(InvalidOperationError):
            account.project_yearly_growth("not-a-dict")  # type: ignore[arg-type]
        with self.assertRaises(InvalidOperationError):
            account.project_yearly_growth({"bonds": 0.04})

    def test_str_includes_portfolio(self) -> None:
        account = InvestmentAccount(self.owner, opening_balance=800, account_id="INV-5005")
        account.invest("stocks", 300)
        text = str(account)
        self.assertIn("InvestmentAccount", text)
        self.assertIn("Evan Wu", text)
        self.assertIn("****5005", text)
        self.assertIn("stocks=300.00", text)
        self.assertIn("bonds=0.00", text)
        self.assertIn("etf=0.00", text)


if __name__ == "__main__":
    unittest.main()
