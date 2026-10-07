"""Investment account with a portfolio split across stocks, bonds, and ETF."""

from __future__ import annotations

from enum import Enum

from bank_account import BankAccount, Currency, InsufficientFundsError, InvalidOperationError, Owner


class SecurityType(Enum):
    STOCKS = "stocks"
    BONDS = "bonds"
    ETF = "etf"


DEMO_GROWTH_RATES = {
    SecurityType.STOCKS.value: 0.10,
    SecurityType.BONDS.value: 0.04,
    SecurityType.ETF.value: 0.07,
}


class InvestmentAccount(BankAccount):
    """Cash account plus a portfolio distributed among security types."""

    def __init__(
        self,
        owner: Owner,
        opening_balance: float = 0.0,
        account_id: str | None = None,
        currency: Currency | str = Currency.RUB,
    ) -> None:
        super().__init__(owner, opening_balance, account_id, currency)
        self.portfolio: dict[str, float] = {
            SecurityType.STOCKS.value: 0.0,
            SecurityType.BONDS.value: 0.0,
            SecurityType.ETF.value: 0.0,
        }

    def withdraw(self, amount: float) -> float:
        """Take cash only. Money already in the portfolio cannot cover a withdrawal."""
        self._check_account_status("withdraw")
        money = self._protect_from_negative(amount, allow_zero=False)
        if money > self._balance:
            invested = round(sum(self.portfolio.values()), 2)
            raise InsufficientFundsError(
                f"need {money}, but cash balance is {self._balance} "
                f"(portfolio {invested} is not withdrawable)"
            )
        return super().withdraw(amount)

    def invest(self, security_type: SecurityType | str, amount: float) -> dict[str, float]:
        """Move cash into a security type. Requires an active account and enough funds."""
        kind = self._validate_security_type(security_type)
        money = self._protect_from_negative(amount, allow_zero=False)
        self.withdraw(money)
        self.portfolio[kind] = round(self.portfolio[kind] + money, 2)
        return dict(self.portfolio)

    def project_yearly_growth(self, growth_rates: dict[str, float]) -> float:
        """Expected annual growth of the invested portfolio using rates per type."""
        if not isinstance(growth_rates, dict):
            raise InvalidOperationError("growth_rates must be a dictionary")
        growth = 0.0
        for kind, invested in self.portfolio.items():
            if invested == 0:
                continue
            if kind not in growth_rates:
                raise InvalidOperationError(f"missing annual rate for {kind}")
            rate = self._validate_growth_rate(kind, growth_rates[kind])
            growth += invested * rate
        return round(growth, 2)

    def get_account_info(self) -> dict[str, object]:
        info = super().get_account_info()
        info["portfolio"] = dict(self.portfolio)
        info["portfolio_total"] = round(sum(self.portfolio.values()), 2)
        return info

    def __str__(self) -> str:
        parts = ", ".join(
            f"{kind}={amount:.2f}" for kind, amount in self.portfolio.items()
        )
        return f"{super().__str__()} | portfolio: {parts}"

    @staticmethod
    def _validate_security_type(security_type: SecurityType | str) -> str:
        if isinstance(security_type, SecurityType):
            return security_type.value
        if isinstance(security_type, str):
            key = security_type.strip().lower()
            try:
                return SecurityType(key).value
            except ValueError as error:
                allowed = ", ".join(item.value for item in SecurityType)
                raise InvalidOperationError(
                    f"security type must be one of: {allowed}"
                ) from error
        raise InvalidOperationError("security type must be SecurityType or str")

    @staticmethod
    def _validate_growth_rate(kind: str, rate: object) -> float:
        if isinstance(rate, bool) or not isinstance(rate, (int, float)):
            raise InvalidOperationError(f"annual rate for {kind} must be a number")
        if rate != rate or rate in (float("inf"), float("-inf")):
            raise InvalidOperationError(f"annual rate for {kind} must be a finite number")
        return float(rate)
