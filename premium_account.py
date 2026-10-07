"""Premium account: higher operation limit, overdraft, and a fixed withdrawal fee."""

from __future__ import annotations

from bank_account import BankAccount, Currency, InsufficientFundsError, InvalidOperationError, Owner


class PremiumAccount(BankAccount):
    """Checking account with a large transaction limit, overdraft, and a fixed fee."""

    DEFAULT_TRANSACTION_LIMIT = 1_000_000.0
    DEFAULT_OVERDRAFT_LIMIT = 1_000.0
    DEFAULT_FIXED_FEE = 5.0

    def __init__(
        self,
        owner: Owner,
        opening_balance: float = 0.0,
        account_id: str | None = None,
        currency: Currency | str = Currency.RUB,
        transaction_limit: float = DEFAULT_TRANSACTION_LIMIT,
        overdraft_limit: float = DEFAULT_OVERDRAFT_LIMIT,
        fixed_fee: float = DEFAULT_FIXED_FEE,
    ) -> None:
        transaction_limit = self._protect_from_negative(transaction_limit, allow_zero=False)
        overdraft_limit = self._protect_from_negative(overdraft_limit, allow_zero=True)
        fixed_fee = self._protect_from_negative(fixed_fee, allow_zero=True)
        super().__init__(owner, opening_balance, account_id, currency)
        self.transaction_limit = transaction_limit
        self.overdraft_limit = overdraft_limit
        self.fixed_fee = fixed_fee

    def deposit(self, amount: float) -> float:
        money = self._protect_from_negative(amount, allow_zero=False)
        self._check_transaction_limit(money)
        return super().deposit(amount)

    def withdraw(self, amount: float) -> float:
        """Take money; may go negative down to -overdraft_limit. Charges fixed_fee."""
        self._check_account_status("withdraw")
        money = self._protect_from_negative(amount, allow_zero=False)
        self._check_transaction_limit(money)
        total = round(money + self.fixed_fee, 2)
        available = round(self._balance + self.overdraft_limit, 2)
        if total > available:
            raise InsufficientFundsError(
                f"need {total}, but available funds are {available}"
            )
        previous = self._balance
        result = round(previous - total, 2)
        if result >= previous:
            raise InvalidOperationError("withdrawal must decrease the balance")
        if result < -self.overdraft_limit:
            raise InsufficientFundsError(
                f"need {total}, but overdraft_limit is {self.overdraft_limit}"
            )
        self._balance = result
        return self._balance

    def get_account_info(self) -> dict[str, object]:
        info = super().get_account_info()
        info["transaction_limit"] = self.transaction_limit
        info["overdraft_limit"] = self.overdraft_limit
        info["fixed_fee"] = self.fixed_fee
        info["available_funds"] = round(self._balance + self.overdraft_limit, 2)
        return info

    def __str__(self) -> str:
        return (
            f"{super().__str__()} | "
            f"limit: {self.transaction_limit:.2f} | "
            f"overdraft: {self.overdraft_limit:.2f} | "
            f"fee: {self.fixed_fee:.2f}"
        )

    def _check_transaction_limit(self, amount: float) -> None:
        if amount > self.transaction_limit:
            raise InvalidOperationError(
                f"amount {amount} exceeds transaction_limit {self.transaction_limit}"
            )
