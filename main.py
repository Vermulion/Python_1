"""Step 3 demo: BankAccount plus Savings / Premium / Investment types."""

from abstract_account import Owner
from bank_account import AccountFrozenError, BankAccount
from investment_account import InvestmentAccount
from premium_account import PremiumAccount
from savings_account import SavingsAccount


def main() -> None:
    active_owner = Owner(
        full_name="Alice Smith",
        email="alice@example.com",
        phone="+79991234567",
    )
    frozen_owner = Owner(
        full_name="Bob Jones",
        email="bob@example.com",
        phone="+79997654321",
    )

    active_account = BankAccount(
        active_owner,
        opening_balance=100,
        account_id="ACC-1001",
        currency="RUB",
    )
    frozen_account = BankAccount(
        frozen_owner,
        opening_balance=200,
        account_id="ACC-2002",
        currency="USD",
    )
    frozen_account.freeze()

    print("Created accounts:")
    print(" ", active_account)
    print(" ", frozen_account)

    print("\nTrying operations on frozen account:")
    try:
        frozen_account.deposit(50)
    except AccountFrozenError as error:
        print(f"  deposit blocked: {error}")
    try:
        frozen_account.withdraw(10)
    except AccountFrozenError as error:
        print(f"  withdraw blocked: {error}")
    print("  frozen account after blocked ops:", frozen_account.get_account_info())

    print("\nAdding money and withdrawing from valid (active) account:")
    print(f"  before: {active_account.get_account_info()}")
    active_account.deposit(50)
    print("  deposited 50")
    active_account.withdraw(20)
    print("  withdrew 20")
    print(f"  after:  {active_account.get_account_info()}")

    savings = SavingsAccount(
        Owner("Carol Lee", email="carol@example.com", phone="+79991112233"),
        opening_balance=1000,
        account_id="SAV-3003",
        min_balance=100,
        monthly_rate=0.01,
    )
    premium = PremiumAccount(
        Owner("Dana Kim", email="dana@example.com", phone="+79994445566"),
        opening_balance=500,
        account_id="PREM-4004",
    )
    investment = InvestmentAccount(
        Owner("Evan Wu", email="evan@example.com", phone="+79997778899"),
        opening_balance=800,
        account_id="INV-5005",
    )

    print("\nExtra account types:")
    print(" ", savings)
    print(" ", premium)
    print(" ", investment)
    savings.apply_monthly_interest()
    print("  savings after monthly interest:", savings.get_account_info())


if __name__ == "__main__":
    main()
