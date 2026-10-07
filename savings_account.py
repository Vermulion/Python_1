"""Step 3: savings account with a minimum balance and monthly interest."""

from __future__ import annotations

from bank_account import BankAccount, Currency, InsufficientFundsError, InvalidOperationError, Owner


class SavingsAccount(BankAccount):
    """Bank account that keeps a floor balance and can earn monthly interest."""

    def __init__(
        self,
        owner: Owner,
        opening_balance: float = 0.0,
        account_id: str | None = None,
        currency: Currency | str = Currency.RUB,
        min_balance: float = 0.0,
        monthly_rate: float = 0.0,
    ) -> None:
        min_balance = self._protect_from_negative(min_balance, allow_zero=True)
        monthly_rate = self._validate_monthly_rate(monthly_rate)
        super().__init__(owner, opening_balance, account_id, currency)
        if self._balance < min_balance:
            raise InvalidOperationError(
                f"opening balance {self._balance} is below min_balance {min_balance}"
            )
        self.min_balance = min_balance
        self.monthly_rate = monthly_rate

    def withdraw(self, amount: float) -> float:
        """Take money without going below min_balance."""
        self._check_account_status("withdraw")
        money = self._protect_from_negative(amount, allow_zero=False)
        remaining = round(self._balance - money, 2)
        if remaining < self.min_balance:
            raise InsufficientFundsError(
                f"need {money}, but balance {self._balance} cannot go below "
                f"min_balance {self.min_balance}"
            )
        return super().withdraw(amount)

    def apply_monthly_interest(self) -> float:
        """Credit this month's return and return the new balance."""
        interest = round(self._balance * self.monthly_rate, 2)
        if interest == 0:
            self._check_account_status("apply interest")
            return self._balance
        return self.deposit(interest)

    def get_account_info(self) -> dict[str, object]:
        info = super().get_account_info()
        info["min_balance"] = self.min_balance
        info["monthly_rate"] = self.monthly_rate
        return info

    def __str__(self) -> str:
        return (
            f"{super().__str__()} | "
            f"min_balance: {self.min_balance:.2f} | "
            f"monthly_rate: {self.monthly_rate:.2%}"
        )

    @staticmethod
    def _validate_monthly_rate(monthly_rate: object) -> float:
        if isinstance(monthly_rate, bool) or not isinstance(monthly_rate, (int, float)):
            raise InvalidOperationError("monthly_rate must be a number")
        if monthly_rate != monthly_rate or monthly_rate in (float("inf"), float("-inf")):
            raise InvalidOperationError("monthly_rate must be a finite number")
        if monthly_rate < 0:
            raise InvalidOperationError("monthly_rate cannot be negative")
        return float(monthly_rate)
